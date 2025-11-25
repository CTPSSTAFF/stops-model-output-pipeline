@ECHO OFF
TITLE Data Processing Pipeline

:START_PIPELINE
REM --- Configuration ---
SET PYTHON_EXE=python
SET MAIN_SCRIPT=main.py
SET LOGFILE=debug_log.txt

REM Set to 1 for development features (detailed error log, re-run option)
REM Set to 0 for standard behavior (simple error message, pause on close)
SET DEBUG_MODE=1

REM --- Start of Script ---
CLS
ECHO.
ECHO   Starting the data processing pipeline...
ECHO   Running %MAIN_SCRIPT%
ECHO --------------------------------------------------

REM Clear the previous log file
IF EXIST "%LOGFILE%" ( DEL "%LOGFILE%" )

REM Run the main Python wrapper and redirect any errors to the log file
%PYTHON_EXE% "%MAIN_SCRIPT%" 2>> "%LOGFILE%"
SET SCRIPT_ERRORLEVEL=%ERRORLEVEL%

REM --- Display Results ---
IF %SCRIPT_ERRORLEVEL% NEQ 0 (
    REM --- ERROR CASE ---
    ECHO.
    ECHO ❌ ERROR: The pipeline failed.
    
    IF "%DEBUG_MODE%"=="1" (
        ECHO debug_log.txt contents:
        TYPE "%LOGFILE%"
    ) ELSE (
        ECHO   Please check the "%LOGFILE%" file for details.
    )
    ECHO --------------------------------------------------
) ELSE (
    REM --- SUCCESS CASE ---
    ECHO.
    ECHO ✅ Pipeline completed.
    ECHO --------------------------------------------------
)

REM --- Final Action: Re-run or Pause/Close ---
IF "%DEBUG_MODE%"=="1" (
    REM In debug mode, offer a choice to re-run or close.
    ECHO.
    CHOICE /C RC /N /M "Press [R] to re-run, or [C] to close the window."
    IF ERRORLEVEL 2 GOTO :EOF
    IF ERRORLEVEL 1 GOTO :START_PIPELINE
) ELSE (
    REM In standard (non-debug) mode, pause.
    ECHO.
    PAUSE
)

GOTO :EOF