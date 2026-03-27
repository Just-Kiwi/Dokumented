@echo off
setlocal enabledelayedexpansion

echo.
echo ========================================
echo   Dokumented Setup - Windows
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://www.python.org/
    exit /b 1
)

REM Check Node
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js 16+ from https://nodejs.org/
    exit /b 1
)

echo Python and Node.js are installed!
echo.

REM Setup Backend
echo Setting up Backend...
cd backend
if not exist venv (
    python -m venv venv
    echo Virtual environment created
)

call venv\Scripts\activate.bat
pip install -r requirements.txt --quiet
echo Backend dependencies installed

setlocal enabledelayedexpansion

REM Create .env file
set CREATE_ENV=y
if exist .env (
    set /p CREATE_ENV=" .env already exists. Overwrite? (y/N): "
)
if /i "%CREATE_ENV%"=="y" (
    echo.
    echo Please enter your API key:
    set /p OPENROUTER_KEY="Enter OPENROUTER_API_KEY: "
    
    (
        echo # API Keys
        echo OPENROUTER_API_KEY=!OPENROUTER_KEY!
        echo OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
        echo.
        echo # Database
        echo DATABASE_URL=sqlite:///./dokumented.db
        echo.
        echo # Application Settings
        echo UPLOAD_FOLDER=./documents
        echo MAX_RETRIES=3
        echo CONFIDENCE_THRESHOLD=0.75
    ) > .env
    echo .env file created
) else (
    echo .env file already exists - skipping
)

endlocal

cd ..

REM Setup Frontend
echo.
echo Setting up Frontend...
cd frontend
if not exist node_modules (
    call npm install --silent
    echo Frontend dependencies installed
) else (
    echo node_modules already exists
)

cd ..

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo To start the application:
echo.
echo 1. Backend (from dokumented/backend):
echo    venv\Scripts\activate
echo    python -m uvicorn main:app --reload --port 8000
echo.
echo 2. Frontend (from dokumented/frontend, in another terminal):
echo    npm run dev
echo.
echo Backend API:        http://localhost:8000
echo Frontend:          http://localhost:5173
echo API Documentation: http://localhost:8000/docs
echo.
echo First-time setup: Your API keys were saved in backend/.env
echo.
endlocal
pause
