#define MyAppName "NexusDB"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "NexusDB"
#define MyAppExeName "nexusdb.exe"

[Setup]
AppId={{A6FCF828-8E57-4CC0-9BF8-7DA2F4616AB7}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\NexusDB
DefaultGroupName=NexusDB
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=output
OutputBaseFilename=NexusDB-{#MyAppVersion}-windows-x64-setup
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
MinVersion=10.0.17763
UninstallDisplayName=NexusDB {#MyAppVersion}
UninstallDisplayIcon={app}\bin\{#MyAppExeName}
SetupLogging=yes
WizardStyle=modern
CloseApplications=no
RestartApplications=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "startservice"; Description: "Iniciar o serviço NexusDB ao concluir"; GroupDescription: "Serviço:"; Flags: checkedonce
Name: "desktopmanual"; Description: "Criar atalho do manual na área de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Dirs]
Name: "{commonappdata}\NexusDB"; Flags: uninsneveruninstall
Name: "{commonappdata}\NexusDB\config"; Flags: uninsneveruninstall
Name: "{commonappdata}\NexusDB\data"; Flags: uninsneveruninstall
Name: "{commonappdata}\NexusDB\backups"; Flags: uninsneveruninstall
Name: "{commonappdata}\NexusDB\logs"; Flags: uninsneveruninstall

[Files]
Source: "..\target\release\nexusdb.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "..\SECURITY.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Docs\Manual_NexusDB_Comandos_e_Exemplos.docx"; DestDir: "{app}\docs"; Flags: ignoreversion

[Icons]
Name: "{group}\Manual do NexusDB"; Filename: "{app}\docs\Manual_NexusDB_Comandos_e_Exemplos.docx"
Name: "{group}\Configuração do NexusDB"; Filename: "notepad.exe"; Parameters: """{commonappdata}\NexusDB\config\nexusdb.env"""
Name: "{group}\Documentação técnica"; Filename: "{app}\docs\README.md"
Name: "{group}\Desinstalar NexusDB"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Manual do NexusDB"; Filename: "{app}\docs\Manual_NexusDB_Comandos_e_Exemplos.docx"; Tasks: desktopmanual

[Registry]
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\nexusdb.exe"; ValueType: string; ValueName: ""; ValueData: "{app}\bin\nexusdb.exe"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\nexusdb.exe"; ValueType: string; ValueName: "Path"; ValueData: "{app}\bin"

[UninstallRun]
Filename: "{app}\bin\nexusdb.exe"; Parameters: "service uninstall"; Flags: runhidden waituntilterminated skipifdoesntexist; RunOnceId: "RemoveNexusDBService"

[Code]
var
  PasswordPage: TInputQueryWizardPage;
  ExistingService: Boolean;

function NexusExe(): String;
begin
  Result := ExpandConstant('{app}\bin\{#MyAppExeName}');
end;

function NexusConfig(): String;
begin
  Result := ExpandConstant('{commonappdata}\NexusDB\config\nexusdb.env');
end;

function RunNexus(const Parameters: String; var ResultCode: Integer): Boolean;
begin
  Result := Exec(NexusExe(), Parameters, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function ServiceExists(): Boolean;
var
  ResultCode: Integer;
begin
  Result := FileExists(NexusExe()) and RunNexus('service status', ResultCode) and
    (ResultCode = 0);
end;

procedure InitializeWizard();
begin
  PasswordPage := CreateInputQueryPage(wpSelectTasks,
    'Credencial administrativa inicial',
    'Defina a senha usada para criar o administrador no primeiro start.',
    'Use pelo menos 12 caracteres. Em uma atualização com banco já inicializado, ' +
    'este valor não altera a senha existente.');
  PasswordPage.Add('Senha administrativa:', True);
  PasswordPage.Add('Confirme a senha:', True);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = PasswordPage.ID then
  begin
    if Length(PasswordPage.Values[0]) < 12 then
    begin
      MsgBox('A senha administrativa deve ter pelo menos 12 caracteres.',
        mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if PasswordPage.Values[0] <> PasswordPage.Values[1] then
    begin
      MsgBox('A confirmação não corresponde à senha informada.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Result := '';
  ExistingService := ServiceExists();
  if ExistingService then
  begin
    if (not RunNexus('service stop', ResultCode)) or (ResultCode <> 0) then
      Result := 'Não foi possível parar o serviço NexusDB para a atualização. ' +
        'Consulte o log do instalador e tente novamente como Administrador.';
  end;
end;

function ReplaceBootstrapPassword(const FileName, Password: String): Boolean;
var
  Lines: TArrayOfString;
  I: Integer;
  Found: Boolean;
begin
  Result := LoadStringsFromFile(FileName, Lines);
  if not Result then Exit;
  Found := False;
  for I := 0 to GetArrayLength(Lines) - 1 do
  begin
    if Pos('NEXUSDB_ADMIN_PASSWORD=', Lines[I]) = 1 then
    begin
      Lines[I] := 'NEXUSDB_ADMIN_PASSWORD=' + Password;
      Found := True;
      Break;
    end;
  end;
  if not Found then
  begin
    SetArrayLength(Lines, GetArrayLength(Lines) + 1);
    Lines[GetArrayLength(Lines) - 1] := 'NEXUSDB_ADMIN_PASSWORD=' + Password;
  end;
  Result := SaveStringsToFile(FileName, Lines, False);
end;

procedure ClearBootstrapPassword();
begin
  ReplaceBootstrapPassword(NexusConfig(), '');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  StartRequested: Boolean;
begin
  if CurStep <> ssPostInstall then Exit;

  if not ExistingService then
  begin
    if (not RunNexus('service install', ResultCode)) or (ResultCode <> 0) then
    begin
      MsgBox('Os arquivos foram instalados, mas o Windows Service não pôde ser ' +
        'registrado. Execute nexusdb.exe service install como Administrador.',
        mbError, MB_OK);
      Exit;
    end;
  end;

  if not ReplaceBootstrapPassword(NexusConfig(), PasswordPage.Values[0]) then
  begin
    MsgBox('Não foi possível gravar a configuração protegida do NexusDB.',
      mbError, MB_OK);
    Exit;
  end;

  StartRequested := WizardIsTaskSelected('startservice') or ExistingService;
  if StartRequested then
  begin
    if RunNexus('service start', ResultCode) and (ResultCode = 0) then
      ClearBootstrapPassword()
    else
      MsgBox('O serviço foi instalado, mas não iniciou. A senha inicial foi ' +
        'mantida no arquivo protegido. Consulte o log em ProgramData\NexusDB\logs.',
        mbError, MB_OK);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    MsgBox('O NexusDB foi removido. Configuração, bancos, backups e logs foram ' +
      'preservados em ProgramData\NexusDB.', mbInformation, MB_OK);
end;
