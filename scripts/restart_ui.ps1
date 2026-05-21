# Restart Scenarius web UI.
. "$PSScriptRoot\ui_common.ps1"

& "$PSScriptRoot\stop_ui.ps1"
Start-Sleep -Seconds 1
& "$PSScriptRoot\start_ui.ps1"
