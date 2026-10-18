//! Local recovery utility. Requires filesystem access to an existing config DB.
//! No server, bootstrap, account creation or network endpoint is started.
use argon2::{
    Argon2, PasswordHash, PasswordHasher, PasswordVerifier,
    password_hash::{SaltString, rand_core::OsRng},
};
use rusqlite::{Connection, OpenFlags, OptionalExtension, TransactionBehavior, params};
use std::{
    io::{self, IsTerminal, Read},
    path::Path,
    time::{Duration, SystemTime, UNIX_EPOCH},
};

fn reset_admin(path: &Path, password: &str) -> Result<(), String> {
    if password.chars().count() < 12 || password.contains(['\r', '\n']) {
        return Err(
            "Use uma nova senha com pelo menos 12 caracteres, sem quebras de linha.".into(),
        );
    }
    if !path.is_file() {
        return Err("Arquivo de configuração não encontrado; nenhum banco foi criado.".into());
    }
    let mut conn = Connection::open_with_flags(path, OpenFlags::SQLITE_OPEN_READ_WRITE)
        .map_err(|e| e.to_string())?;
    conn.busy_timeout(Duration::from_secs(10))
        .map_err(|e| e.to_string())?;
    let tx = conn
        .transaction_with_behavior(TransactionBehavior::Immediate)
        .map_err(|e| e.to_string())?;
    let current: Option<String> = tx
        .query_row(
            "SELECT password_hash FROM users WHERE username='admin' AND active=1 AND role='admin'",
            [],
            |row| row.get(0),
        )
        .optional()
        .map_err(|e| format!("Arquivo não contém a configuração esperada: {e}"))?;
    let current = current.ok_or("Administrador ativo não encontrado; nada foi alterado.")?;
    if PasswordHash::new(&current).ok().is_some_and(|hash| {
        Argon2::default()
            .verify_password(password.as_bytes(), &hash)
            .is_ok()
    }) {
        return Err("Escolha uma senha diferente da atual.".into());
    }
    let salt = SaltString::generate(&mut OsRng);
    let hash = Argon2::default()
        .hash_password(password.as_bytes(), &salt)
        .map_err(|e| e.to_string())?
        .to_string();
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|e| e.to_string())?
        .as_secs() as i64;
    let changed = tx.execute(
        "UPDATE users SET password_hash=?1, password_changed_at=?2, failed_attempts=0, locked=0, updated_at=CURRENT_TIMESTAMP WHERE username='admin' AND active=1 AND role='admin'",
        params![hash,now]).map_err(|e| e.to_string())?;
    if changed != 1 {
        return Err("A recuperação não encontrou exatamente um administrador.".into());
    }
    tx.commit().map_err(|e| e.to_string())
}

fn run() -> Result<(), String> {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if args.len() != 2 || args[0] != "--config-db" {
        return Err("Use tools/reset_admin_password.ps1 -DataRoot <pasta-de-dados>.".into());
    }
    if io::stdin().is_terminal() {
        return Err("Use o script PowerShell para digitar a senha de forma oculta.".into());
    }
    let mut password = String::new();
    io::stdin()
        .read_to_string(&mut password)
        .map_err(|_| "Não foi possível ler a nova senha.")?;
    let password = password.strip_suffix('\n').unwrap_or(&password);
    let password = password.strip_suffix('\r').unwrap_or(password);
    reset_admin(Path::new(&args[1]), password)?;
    println!("Senha do admin redefinida e conta desbloqueada. A nova senha já está ativa.");
    Ok(())
}

fn main() {
    if let Err(e) = run() {
        eprintln!("{e}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn fixture() -> std::path::PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "nexusdb-recovery-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("config.sqlite");
        let conn = Connection::open(&path).unwrap();
        conn.execute_batch("CREATE TABLE users(username TEXT PRIMARY KEY,role TEXT,password_hash TEXT,password_changed_at INTEGER,failed_attempts INTEGER,locked INTEGER,active INTEGER,updated_at TEXT);
            INSERT INTO users VALUES('admin','admin','old-hash',0,5,1,1,'old');
            INSERT INTO users VALUES('other','user','unchanged',0,0,0,1,'old');
            CREATE TABLE database_access(username TEXT, access_type TEXT);
            INSERT INTO database_access VALUES('admin','ADMIN');").unwrap();
        path
    }
    #[test]
    fn resets_locked_admin_without_touching_other_accounts_or_permissions() {
        let path = fixture();
        reset_admin(&path, "Recovery-Test-Password!").unwrap();
        let conn = Connection::open(&path).unwrap();
        let (hash,locked,failed,changed): (String,i64,i64,i64) = conn.query_row("SELECT password_hash,locked,failed_attempts,password_changed_at FROM users WHERE username='admin'",[],|r|Ok((r.get(0)?,r.get(1)?,r.get(2)?,r.get(3)?))).unwrap();
        assert!(
            Argon2::default()
                .verify_password(
                    b"Recovery-Test-Password!",
                    &PasswordHash::new(&hash).unwrap()
                )
                .is_ok()
        );
        assert_eq!((locked, failed), (0, 0));
        assert!(changed > 0);
        assert_eq!(
            conn.query_row(
                "SELECT password_hash FROM users WHERE username='other'",
                [],
                |r| r.get::<_, String>(0)
            )
            .unwrap(),
            "unchanged"
        );
        assert_eq!(
            conn.query_row("SELECT access_type FROM database_access", [], |r| r
                .get::<_, String>(0))
                .unwrap(),
            "ADMIN"
        );
        assert!(reset_admin(&path, "Recovery-Test-Password!").is_err());
    }
    #[test]
    fn wrong_paths_short_passwords_and_inactive_admins_do_not_change_data() {
        let path = fixture();
        let missing = path.with_file_name("missing.sqlite");
        assert!(reset_admin(&missing, "Recovery-Test-Password!").is_err());
        assert!(!missing.exists());
        assert!(reset_admin(&path, "short").is_err());
        let conn = Connection::open(&path).unwrap();
        conn.execute("UPDATE users SET active=0 WHERE username='admin'", [])
            .unwrap();
        assert!(reset_admin(&path, "Recovery-Test-Password!").is_err());
        assert_eq!(
            conn.query_row(
                "SELECT password_hash FROM users WHERE username='admin'",
                [],
                |r| r.get::<_, String>(0)
            )
            .unwrap(),
            "old-hash"
        );
    }
}
