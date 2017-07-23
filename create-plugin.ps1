rm __init__.py

cp device_init.py __init__.py
Write-Zip -Path .\container.py,.\common.py,.\device,.\plugin-import-name-kobotouch_extended.txt,.\__init__.py,.\css,.\translations -OutputPath KoboTouchExtended.zip
rm __init__.py

cp conversion_out_init.py __init__.py
cp .\conversion\output_init.py .\conversion\__init__.py
Write-Zip -Path .\container.py,.\common.py,.\conversion\__init__.py,.\conversion\kepub_output.py,.\conversion\output_config.py,.\plugin-import-name-kepubout.txt,.\__init__.py,.\css,.\translations -OutputPath "KePub Output.zip"
rm __init__.py

cp conversion_in_init.py __init__.py
cp .\conversion\input_init.py .\conversion\__init__.py
Write-Zip -Path .\container.py,.\common.py,.\conversion\__init__.py,.\conversion\kepub_input.py,.\conversion\input_config.py,.\plugin-import-name-kepubin.txt,.\__init__.py,.\css,.\translations -OutputPath "KePub Input.zip"
rm __init__.py
rm .\conversion\__init__.py

cp md_reader_init.py __init__.py
Write-Zip -Path .\__init__.py,.\translations,.\metadata\__init__.py,.\metadata\reader.py,.\common.py,.\plugin-import-name-kepubmdreader.txt "KePub Metadata Reader.zip"
rm __init__.py

cp md_writer_init.py __init__.py
Write-Zip -Path .\__init__.py,.\translations,.\metadata\__init__.py,.\metadata\writer.py,.\common.py,.\plugin-import-name-kepubmdwriter.txt "KePub Metadata Writer.zip"
rm __init__.py

Set-Content -Path __init__.py -Value $null
