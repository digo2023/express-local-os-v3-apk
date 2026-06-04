[app]
title = Express Local OS
package.name = expresslocalos
package.domain = org.maicon.express
source.dir = .
source.include_exts = py,png,jpg,kv,db,json,txt
version = 3.0.0
requirements = python3,kivy==2.3.0
orientation = portrait
fullscreen = 0
android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 35
android.minapi = 23
android.ndk = 25b
android.archs = arm64-v8a,armeabi-v7a
android.allow_backup = True
android.accept_sdk_license = True
p4a.branch = develop

[buildozer]
log_level = 2
warn_on_root = 0
