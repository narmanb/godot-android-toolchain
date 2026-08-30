from pathlib import Path

src = Path('app/src/main/java/com/narmanb/ikemeninstaller/InstallerActivityV17.java')
dst = Path('app/src/main/java/com/narmanb/ikemeninstaller/InstallerActivityV18.java')
text = src.read_text(encoding='utf-8')

text = text.replace('public class InstallerActivityV17 extends Activity {', 'public class InstallerActivityV18 extends Activity {', 1)
text = text.replace(
    'v1.7 — keeps every v1.6 feature and adds a separate deep scan for already-installed characters that traces State -1 command usage to find moves the basic generator can miss.',
    'v1.8 — keeps all v1.7 features, adds ZIP/RAR/7Z installs, safe character removal, and fixes repair duplicate detection for existing roster shortcuts.',
    1,
)

# Android dialog + 7z support imports.
text = text.replace('import android.app.Activity;\n', 'import android.app.Activity;\nimport android.app.AlertDialog;\n', 1)
text = text.replace(
    'import com.github.junrar.Junrar;\n',
    'import com.github.junrar.Junrar;\nimport org.apache.commons.compress.archivers.sevenz.SevenZArchiveEntry;\nimport org.apache.commons.compress.archivers.sevenz.SevenZFile;\n',
    1,
)

# Make the UI advertise 7Z and add a separate removal tool without changing existing actions.
text = text.replace('ZIP / RAR', 'ZIP / RAR / 7Z')
old_ui = '''        Button deepMovelistRepair = button("Deep-scan installed command lists", true);\n        deepMovelistRepair.setOnClickListener(v -> deepScanInstalledMovelists());\n        root.addView(deepMovelistRepair);\n\n        addHeading(root, "Stages");'''
new_ui = '''        Button deepMovelistRepair = button("Deep-scan installed command lists", true);\n        deepMovelistRepair.setOnClickListener(v -> deepScanInstalledMovelists());\n        root.addView(deepMovelistRepair);\n\n        Button removeCharacter = button("Remove installed character", true);\n        removeCharacter.setOnClickListener(v -> showRemoveCharacterPicker());\n        root.addView(removeCharacter);\n\n        addHeading(root, "Stages");'''
if old_ui not in text:
    raise SystemExit('v1.8 remove-character UI insertion point not found')
text = text.replace(old_ui, new_ui, 1)

# Add 7z MIME hint to Android's picker.
old_mimes = '''                "application/vnd.rar", "application/x-rar-compressed",\n                "application/octet-stream"'''
new_mimes = '''                "application/vnd.rar", "application/x-rar-compressed",\n                "application/x-7z-compressed",\n                "application/octet-stream"'''
if old_mimes not in text:
    raise SystemExit('archive MIME insertion point not found')
text = text.replace(old_mimes, new_mimes, 1)

# Replace archive extraction so ZIP, RAR, and 7Z all flow through the same install logic.
archive_start = text.index('    private String installArchive(Uri archiveUri, String name, GameFiles g, boolean stage) throws Exception {')
archive_end = text.index('    private void installUnpackedCharacter(Uri treeUri) {', archive_start)
new_archive = r'''    private String installArchive(Uri archiveUri, String name, GameFiles g, boolean stage) throws Exception {
        String lower = name.toLowerCase(Locale.ROOT);
        boolean zip = lower.endsWith(".zip");
        boolean rar = lower.endsWith(".rar");
        boolean seven = lower.endsWith(".7z");
        if (!zip && !rar && !seven) {
            throw new IOException("Choose a .zip, .rar, or .7z archive.");
        }

        File temp = tempDir();
        File sevenTemp = null;
        try {
            try (InputStream raw = getContentResolver().openInputStream(archiveUri)) {
                if (raw == null) throw new IOException("Android could not open the archive.");
                if (zip) {
                    extractZip(raw, temp);
                } else if (rar) {
                    Junrar.extract(new BufferedInputStream(raw), temp);
                } else {
                    sevenTemp = File.createTempFile("ikemen-archive-", ".7z", getCacheDir());
                    try (OutputStream out = new BufferedOutputStream(new FileOutputStream(sevenTemp))) {
                        copyStream(raw, out);
                    }
                    extractSevenZip(sevenTemp, temp);
                }
            }
            return stage ? installStageFromLocal(temp, stripExtension(name), g)
                    : installCharacterFromLocal(temp, stripExtension(name), g);
        } finally {
            if (sevenTemp != null) sevenTemp.delete();
            deleteTree(temp);
        }
    }

    private void extractSevenZip(File archive, File dest) throws IOException {
        String root = dest.getCanonicalPath() + File.separator;
        byte[] buffer = new byte[8192];
        try (SevenZFile seven = new SevenZFile(archive)) {
            SevenZArchiveEntry entry;
            while ((entry = seven.getNextEntry()) != null) {
                String name = entry.getName();
                if (name == null || name.isBlank()) continue;
                File out = new File(dest, name.replace('\\', '/'));
                String canonical = out.getCanonicalPath();
                if (!canonical.startsWith(root)) {
                    throw new IOException("Blocked unsafe 7Z path: " + name);
                }
                if (entry.isDirectory()) {
                    if (!out.exists() && !out.mkdirs()) throw new IOException("Could not create 7Z directory: " + name);
                    continue;
                }
                File parent = out.getParentFile();
                if (parent != null && !parent.exists() && !parent.mkdirs()) {
                    throw new IOException("Could not create 7Z directory for: " + name);
                }
                try (OutputStream fileOut = new BufferedOutputStream(new FileOutputStream(out))) {
                    int n;
                    while ((n = seven.read(buffer)) > 0) fileOut.write(buffer, 0, n);
                }
            }
        }
    }

'''
text = text[:archive_start] + new_archive + text[archive_end:]

# Fix repair/register duplicate detection. For Characters, a shortcut such as "kfm720"
# and an explicit DEF such as "kfm720/kfm.def" refer to the same top-level character folder.
roster_start = text.index('    private static boolean rosterContains(String text, String entry, String section) {')
roster_end = text.index('    private DefPick findBestCharacterDef(File root, String hint) throws IOException {', roster_start)
new_roster = r'''    private static boolean rosterContains(String text, String entry, String section) {
        String wanted = canonicalRosterEntry(entry, section);
        boolean inSection = false;
        for (String raw : text.split("\\r?\\n")) {
            String t = raw.trim();
            if (t.equalsIgnoreCase("[" + section + "]")) {
                inSection = true;
                continue;
            }
            if (inSection && t.startsWith("[") && t.endsWith("]")) break;
            if (!inSection) continue;
            String clean = stripComment(raw).trim();
            if (clean.isEmpty()) continue;
            String first = clean.split(",", 2)[0].trim();
            if (canonicalRosterEntry(first, section).equalsIgnoreCase(wanted)) return true;
        }
        return false;
    }

    private static String canonicalRosterEntry(String value, String section) {
        String clean = cleanPath(value == null ? "" : value.trim());
        if (!section.equalsIgnoreCase("Characters")) return clean;
        if (clean.toLowerCase(Locale.ROOT).startsWith("chars/")) clean = clean.substring(6);
        int slash = clean.indexOf('/');
        if (slash >= 0) return clean.substring(0, slash);
        if (clean.toLowerCase(Locale.ROOT).endsWith(".def")) return stripExtension(clean);
        return clean;
    }

'''
text = text[:roster_start] + new_roster + text[roster_end:]

# Add safe, explicit character removal. Default action only edits the roster; file deletion is
# separately chosen and is suppressed if other roster entries still reference the same folder.
remove_insert = '    private void deepScanInstalledMovelists() {'
if remove_insert not in text:
    raise SystemExit('remove-character helper insertion point not found')
remove_helpers = r'''    private void showRemoveCharacterPicker() {
        busy("Reading registered characters…");
        worker.execute(() -> {
            try {
                GameFiles g = resolveGameFiles();
                List<RosterCharacter> entries = parseRosterCharacters(readText(g.selectFile));
                if (entries.isEmpty()) {
                    success("No removable character entries were found in [Characters].");
                    return;
                }
                String[] labels = new String[entries.size()];
                for (int i = 0; i < entries.size(); i++) labels[i] = entries.get(i).display;
                runOnUiThread(() -> {
                    refreshUi();
                    statusView.setText("Choose a character entry to remove.");
                    new AlertDialog.Builder(this)
                            .setTitle("Remove character")
                            .setItems(labels, (dialog, which) -> showRemoveCharacterMode(entries.get(which)))
                            .setNegativeButton("Cancel", null)
                            .show();
                });
            } catch (Exception e) {
                fail("Could not read the character roster.\n\n" + message(e));
            }
        });
    }

    private void showRemoveCharacterMode(RosterCharacter entry) {
        String[] options = {"Remove from roster only", "Remove from roster + delete files"};
        new AlertDialog.Builder(this)
                .setTitle(entry.display)
                .setItems(options, (dialog, which) -> {
                    if (which == 0) {
                        removeCharacterEntry(entry, false);
                    } else {
                        new AlertDialog.Builder(this)
                                .setTitle("Delete character files too?")
                                .setMessage("This permanently deletes the character folder when no other roster entry uses it. A select.def backup is made first.")
                                .setPositiveButton("Delete files", (d, w) -> removeCharacterEntry(entry, true))
                                .setNegativeButton("Cancel", null)
                                .show();
                    }
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    private void removeCharacterEntry(RosterCharacter choice, boolean deleteFiles) {
        busy("Removing character…");
        worker.execute(() -> {
            try {
                GameFiles g = resolveGameFiles();
                String original = readText(g.selectFile);
                String updated = removeSelectedCharacterLine(original, choice);
                if (updated.equals(original)) throw new IOException("That roster entry could not be found. It may have changed since the list was opened.");

                String stamp = new SimpleDateFormat("yyyyMMdd-HHmmss-SSS", Locale.US).format(new Date());
                DocumentFile backup = createExactFile(g.selectDir, "select.def.backup-" + stamp);
                writeText(backup, original);
                writeText(g.selectFile, updated);

                String fileResult = "Files kept in chars/.";
                if (deleteFiles) {
                    String folderName = characterFolderForEntry(choice.firstField);
                    int remainingRefs = countCharacterFolderRefs(updated, folderName);
                    if (folderName.isBlank()) {
                        fileResult = "Roster removed; character folder could not be determined, so files were kept.";
                    } else if (remainingRefs > 0) {
                        fileResult = "Roster removed; files were kept because " + remainingRefs + " other roster entr" + (remainingRefs == 1 ? "y still uses" : "ies still use") + " that folder.";
                    } else {
                        DocumentFile folder = childExact(g.charsDir, folderName);
                        if (folder != null && folder.isDirectory()) {
                            if (!deleteSafTree(folder)) fileResult = "Roster removed, but Android could not fully delete the character folder.";
                            else fileResult = "Character folder deleted from chars/.";
                        } else {
                            fileResult = "Roster removed; no matching character folder was found to delete.";
                        }
                    }
                }

                success("Character removed ✓\n\nEntry: " + choice.firstField
                        + "\n" + fileResult
                        + "\nBackup: " + backup.getName());
            } catch (Exception e) {
                fail("Character removal failed.\n\n" + message(e));
            }
        });
    }

    private static List<RosterCharacter> parseRosterCharacters(String text) {
        List<RosterCharacter> out = new ArrayList<>();
        boolean inCharacters = false;
        int ordinal = 0;
        for (String raw : text.split("\\r?\\n", -1)) {
            String trimmed = raw.trim();
            if (trimmed.equalsIgnoreCase("[Characters]")) {
                inCharacters = true;
                continue;
            }
            if (inCharacters && trimmed.startsWith("[") && trimmed.endsWith("]")) break;
            if (!inCharacters) continue;
            String clean = stripComment(raw).trim();
            if (clean.isEmpty()) continue;
            String first = clean.split(",", 2)[0].trim();
            if (first.equalsIgnoreCase("randomselect")) continue;
            String lower = first.toLowerCase(Locale.ROOT);
            if (lower.startsWith("randomselect,")) continue;
            ordinal++;
            out.add(new RosterCharacter(raw, first, ordinal + ". " + first));
        }
        return out;
    }

    private static String removeSelectedCharacterLine(String original, RosterCharacter choice) {
        String eol = original.contains("\r\n") ? "\r\n" : "\n";
        List<String> lines = new ArrayList<>(Arrays.asList(original.split("\\r?\\n", -1)));
        boolean inCharacters = false;
        for (int i = 0; i < lines.size(); i++) {
            String trimmed = lines.get(i).trim();
            if (trimmed.equalsIgnoreCase("[Characters]")) {
                inCharacters = true;
                continue;
            }
            if (inCharacters && trimmed.startsWith("[") && trimmed.endsWith("]")) break;
            if (!inCharacters) continue;
            if (lines.get(i).equals(choice.rawLine)) {
                lines.remove(i);
                return String.join(eol, lines);
            }
        }
        // Fallback if whitespace/comment formatting changed after the picker was opened.
        inCharacters = false;
        for (int i = 0; i < lines.size(); i++) {
            String trimmed = lines.get(i).trim();
            if (trimmed.equalsIgnoreCase("[Characters]")) {
                inCharacters = true;
                continue;
            }
            if (inCharacters && trimmed.startsWith("[") && trimmed.endsWith("]")) break;
            if (!inCharacters) continue;
            String clean = stripComment(lines.get(i)).trim();
            if (clean.isEmpty()) continue;
            String first = clean.split(",", 2)[0].trim();
            if (first.equalsIgnoreCase(choice.firstField)) {
                lines.remove(i);
                return String.join(eol, lines);
            }
        }
        return original;
    }

    private static String characterFolderForEntry(String firstField) {
        String clean = cleanPath(firstField == null ? "" : firstField.trim());
        if (clean.toLowerCase(Locale.ROOT).startsWith("chars/")) clean = clean.substring(6);
        int slash = clean.indexOf('/');
        if (slash >= 0) clean = clean.substring(0, slash);
        else if (clean.toLowerCase(Locale.ROOT).endsWith(".def")) clean = stripExtension(clean);
        if (clean.equals(".") || clean.equals("..") || clean.contains("/")) return "";
        return clean;
    }

    private static int countCharacterFolderRefs(String roster, String folderName) {
        if (folderName == null || folderName.isBlank()) return 0;
        int count = 0;
        boolean inCharacters = false;
        for (String raw : roster.split("\\r?\\n")) {
            String t = raw.trim();
            if (t.equalsIgnoreCase("[Characters]")) {
                inCharacters = true;
                continue;
            }
            if (inCharacters && t.startsWith("[") && t.endsWith("]")) break;
            if (!inCharacters) continue;
            String clean = stripComment(raw).trim();
            if (clean.isEmpty()) continue;
            String first = clean.split(",", 2)[0].trim();
            if (first.equalsIgnoreCase("randomselect")) continue;
            if (characterFolderForEntry(first).equalsIgnoreCase(folderName)) count++;
        }
        return count;
    }

    private boolean deleteSafTree(DocumentFile file) {
        boolean ok = true;
        if (file.isDirectory()) {
            for (DocumentFile child : file.listFiles()) ok &= deleteSafTree(child);
        }
        return file.delete() && ok;
    }

'''
text = text.replace(remove_insert, remove_helpers + remove_insert, 1)

# Add the picker row model beside the existing helper inner classes.
inner_marker = '    private static class CommandEntry {'
if inner_marker not in text:
    raise SystemExit('RosterCharacter inner-class insertion point not found')
inner = '''    private static class RosterCharacter {\n        final String rawLine;\n        final String firstField;\n        final String display;\n        RosterCharacter(String rawLine, String firstField, String display) {\n            this.rawLine = rawLine;\n            this.firstField = firstField;\n            this.display = display;\n        }\n    }\n\n'''
text = text.replace(inner_marker, inner + inner_marker, 1)

dst.write_text(text, encoding='utf-8')
print(f'Wrote {dst} ({len(text)} bytes)')
