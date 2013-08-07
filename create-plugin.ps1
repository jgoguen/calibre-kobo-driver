rm __init__.py

cp device_init.py __init__.py
Write-Zip -Path .\container.py,.\common.py,.\device,.\plugin-import-name-kobotouch_extended.txt,.\__init__.py,.\css -OutputPath KoboTouchExtended.zip
rm __init__.py

cp conversion_init.py __init__.py
Write-Zip -Path .\container.py,.\common.py,.\conversion,.\plugin-import-name-kobotouch_extended.txt,.\__init__.py,.\css -OutputPath KoboTouchExtended.zip
rm __init__.py

Set-Content -Path __init__.py -Value $null