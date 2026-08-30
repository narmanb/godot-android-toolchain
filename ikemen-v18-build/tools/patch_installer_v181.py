from pathlib import Path

src = Path('app/src/main/java/com/narmanb/ikemeninstaller/InstallerActivityV18.java')
dst = Path('app/src/main/java/com/narmanb/ikemeninstaller/InstallerActivityV181.java')
text = src.read_text(encoding='utf-8')

text = text.replace('public class InstallerActivityV18 extends Activity {', 'public class InstallerActivityV181 extends Activity {', 1)
text = text.replace(
    'v1.8 — keeps all v1.7 features, adds ZIP/RAR/7Z installs, safe character removal, and fixes repair duplicate detection for existing roster shortcuts.',
    'v1.8.1 — keeps all v1.8 features and fixes Android archive picking so ZIP, RAR, and 7Z files remain selectable regardless of MIME type.',
    1,
)

old = '''        i.setType("*/*");\n        i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, multiple);\n        i.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{\n                "application/zip", "application/x-zip-compressed",\n                "application/vnd.rar", "application/x-rar-compressed",\n                "application/x-7z-compressed",\n                "application/octet-stream"\n        });\n        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);'''
new = '''        // Do not MIME-filter archives here. Android file providers identify .rar/.7z\n        // inconsistently, which can grey out files the installer can actually extract.\n        // installArchive() validates the selected filename as .zip/.rar/.7z instead.\n        i.setType("*/*");\n        i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, multiple);\n        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);'''
if old not in text:
    raise SystemExit('archive picker MIME block not found')
text = text.replace(old, new, 1)

dst.write_text(text, encoding='utf-8')
print(f'Wrote {dst} ({len(text)} bytes)')
