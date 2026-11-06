@echo off
cd /d "%~dp0"
tasklist /fi "imagename eq start_server.exe" /nh | find /i "start_server.exe" >nul || start "" /min start_server.exe
tasklist /fi "imagename eq start_client.exe" /nh | find /i "start_client.exe" >nul || start "" /min start_client.exe
