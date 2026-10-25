$ErrorActionPreference = 'Stop'
$base = if ($env:VITE_API_BASE_URL) { $env:VITE_API_BASE_URL } else { 'http://localhost:8000/api' }
Write-Host '1. Hardware online'
Invoke-RestMethod "$base/devices" | ConvertTo-Json -Depth 6
Write-Host '2. S3 crack detected'
$alerts = Invoke-RestMethod "$base/alerts?severity=S3"
$alert = @($alerts.items)[0]
if (-not $alert) { throw 'No S3 alert returned by the backend.' }
$alert | ConvertTo-Json -Depth 6
Write-Host '3. Track switch recommendation'
Invoke-RestMethod "$base/switch/status" | ConvertTo-Json -Depth 8
Write-Host '4. Admin assigns the acknowledged alert'
$workers = Invoke-RestMethod "$base/workers"
$worker = @($workers.items)[0]
$task = Invoke-RestMethod -Method Post "$base/tasks" -ContentType 'application/json' -Body (@{ alert_id = $alert.id; worker_id = $worker.id; status = 'ASSIGNED'; priority = $alert.severity } | ConvertTo-Json)
$task | ConvertTo-Json -Depth 6
Write-Host '5. Worker completes repair'
Invoke-RestMethod -Method Put "$base/tasks/$($task.id)/status" -ContentType 'application/json' -Body (@{ status = 'ACCEPTED' } | ConvertTo-Json) | Out-Null
Invoke-RestMethod -Method Put "$base/tasks/$($task.id)/status" -ContentType 'application/json' -Body (@{ status = 'IN_PROGRESS' } | ConvertTo-Json) | Out-Null
$photo = Join-Path $env:TEMP 'amrin-demo-repair.jpg'
if (-not (Test-Path $photo)) { [IO.File]::WriteAllBytes($photo, [byte[]](255,216,255,224)) }
Invoke-RestMethod -Method Post "$base/tasks/$($task.id)/evidence" -Form @{ file = Get-Item $photo; notes = 'Demo repair evidence' } | Out-Null
Invoke-RestMethod -Method Put "$base/tasks/$($task.id)/status" -ContentType 'application/json' -Body (@{ status = 'COMPLETED' } | ConvertTo-Json) | Out-Null
Write-Host '6. Alert resolved'
Invoke-RestMethod -Method Post "$base/alerts/$($alert.id)/resolve" -ContentType 'application/json' -Body '{}' | ConvertTo-Json -Depth 6
