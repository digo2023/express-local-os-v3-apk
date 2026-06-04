[app]
title = Gestao Estoque Express
package.name = gestaoestoqueexpress
package.domain = br.com.expresscolorado
version = 1.0
icon.filename = icon.png

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,txt,md,db,sqlite,sql,pdf,csv,xlsx,xls,json,ttf
source.include_patterns = sistema_express/**,reportlab/**,.github/**,icon.png
source.exclude_dirs = .git,bin,build,.buildozer,__pycache__,.pytest_cache,backups_atualizacao
source.exclude_exts = pyc,pyo

# Python Android fixado em 3.10 para evitar falha de compilação do Kivy contra Python 3.14.
# A documentação do python-for-android permite fixar python3 e hostpython3 nos requirements.
requirements = python3==3.10.13,hostpython3==3.10.13,kivy==2.3.0

orientation = portrait
fullscreen = 0

android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES,READ_MEDIA_VIDEO,READ_MEDIA_AUDIO
android.api = 33
android.minapi = 26
android.ndk_api = 26
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a

# Não usar p4a.branch=develop.
# O workflow limpa cache para impedir reaproveitamento de Python 3.14 em builds antigos.

[buildozer]
log_level = 2
warn_on_root = 0
