rm __init__.py

cp device_init.py __init__.py
Write-Zip -Path .\container.py,.\common.py,.\device,.\plugin-import-name-kobotouch_extended.txt,.\__init__.py,.\css,.\translations -OutputPath KoboTouchExtended.zip
rm __init__.py

cp conversion_init.py __init__.py
Write-Zip -Path .\container.py,.\common.py,.\conversion,.\plugin-import-name-koboconversion.txt,.\__init__.py,.\css,.\translations -OutputPath "KePub Output.zip"
rm __init__.py

cp md_reader_init.py __init__.py
Write-Zip -Path .\__init__.py,.\translations,.\metadata\__init__.py,.\metadata\reader.py,.\common.py,.\plugin-import-name-kepubmdreader.txt "Read KEPUB metadata.zip"

cp md_writer_init.py __init__.py
Write-Zip -Path .\__init__.py,.\translations,.\metadata\__init__.py,.\metadata\writer.py,.\common.py,.\plugin-import-name-kepubmdwriter.txt "Set KEPUB metadata.zip"

Set-Content -Path __init__.py -Value $null
