@echo off
title IES System Launcher
echo ========================================================
echo Starting Invoice Extraction and Verification System (IES)
echo ========================================================

:: 1. Ensure PostgreSQL is running
echo Checking PostgreSQL container...
docker start ies-local-postgres-1 >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
  echo Container not found by name, attempting docker compose up...
  cd /d C:\IES && docker compose up -d
)

:: Wait for PostgreSQL to be ready on port 5432
echo Waiting for database on port 5432...
:check_pg
powershell -Command "try { (New-Object Net.Sockets.TcpClient).Connect('127.0.0.1', 5432); exit 0 } catch { exit 1 }"
if %ERRORLEVEL% NEQ 0 (
  timeout /t 1 /nobreak >nul
  goto check_pg
)
echo PostgreSQL is ready!

:: 2. Start Fastify API Backend (Port 8080)
echo Starting API Backend on http://localhost:8080...
start "IES - API Backend (Port 8080)" cmd /k "cd /d C:\IES\backend && pnpm tsx --env-file=../.env src/services/api/server.ts"

:: Wait for API backend to listen on port 8080
:check_api
powershell -Command "try { (New-Object Net.Sockets.TcpClient).Connect('127.0.0.1', 8080); exit 0 } catch { exit 1 }"
if %ERRORLEVEL% NEQ 0 (
  timeout /t 1 /nobreak >nul
  goto check_api
)
echo API Backend is ready!

:: 3. Start Background Extraction Processor (Port 8081)
echo Starting Background Processor Worker on http://localhost:8081...
start "IES - Extraction Processor (Port 8081)" cmd /k "cd /d C:\IES\backend && pnpm tsx --env-file=../.env src/services/processor/server.ts"

:: 4. Start Vite React Frontend (Port 5173)
echo Starting Frontend UI on http://localhost:5173...
start "IES - Vite Frontend (Port 5173)" cmd /k "cd /d C:\IES\frontend && pnpm dev"

echo ========================================================
echo All services successfully launched!
echo - API Backend:       http://localhost:8080
echo - Processor Worker:  http://localhost:8081
echo - Frontend UI:       http://localhost:5173
echo ========================================================
pause
