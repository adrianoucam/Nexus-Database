set "NEXUSDB_HA_SECRET=123456789012345678901234567890123"


python3 import_supply_chain_nexusdb.py   --csv "Car_SupplyChainManagementDataSet.csv"   --password "MinhaSenha123"   --database SUPPLY_CHAIN_TEST   --limit 100



$headers = @{
    "X-User" = "admin"
    "X-Pass" = "MinhaSenha123"
}

$body = @{
    new_password = "123456789012345678901234567890123"
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri "http://127.0.0.1:7474/db/auth/password/change" `
    -Method Post `
    -Headers $headers `
    -ContentType "application/json; charset=utf-8" `
    -Body $body