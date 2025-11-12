(Get-Content 'frontend/src/pages/Automation.tsx' | Select-Object @{Name='LineNumber';Expression={=(+1);}} , @{Name='Text';Expression={}})
