@echo off
setlocal

pushd "%~dp0"

echo Syncing submodule configuration...
git submodule sync --recursive
if errorlevel 1 goto :fail

echo Initializing and updating submodules to remote...
git submodule update --remote --recursive --init
if errorlevel 1 goto :fail

echo Submodule update complete.
popd
exit /b 0

:fail
echo Submodule pull failed.
popd
exit /b 1
