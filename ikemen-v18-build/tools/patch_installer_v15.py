from pathlib import Path

src = Path('app/src/main/java/com/narmanb/ikemeninstaller/InstallerActivityV14.java')
dst = Path('app/src/main/java/com/narmanb/ikemeninstaller/InstallerActivityV15.java')
text = src.read_text(encoding='utf-8')

text = text.replace('public class InstallerActivityV14 extends Activity {', 'public class InstallerActivityV15 extends Activity {', 1)
text = text.replace(
    'v1.4 — exact filename preservation, separate single/multiple character installs, and stage installation with bundled-music handling.',
    'v1.5 — exact filename preservation, single/multiple character and stage installs, plus automatic IKEMEN command-list generation from MUGEN .cmd files.',
    1,
)

old_ui = '''        Button charRepair = button("Repair/register characters already in chars/", true);\n        charRepair.setOnClickListener(v -> repairExistingCharacters());\n        root.addView(charRepair);\n\n        addHeading(root, "Stages");'''
new_ui = '''        Button charRepair = button("Repair/register characters already in chars/", true);\n        charRepair.setOnClickListener(v -> repairExistingCharacters());\n        root.addView(charRepair);\n\n        Button movelistRepair = button("Generate missing command lists", true);\n        movelistRepair.setOnClickListener(v -> generateMissingMovelists());\n        root.addView(movelistRepair);\n\n        addHeading(root, "Stages");'''
if old_ui not in text:
    raise SystemExit('UI insertion point not found')
text = text.replace(old_ui, new_ui, 1)

text = text.replace(
    'Files are copied with their original names exactly — no automatic .txt suffixes. Stage packages are registered under [ExtraStages]. If a package has a configured BGM, or exactly one bundled audio file with a blank BGM, the installer copies that audio into sound/ and points the stage to it.',
    'Files are copied with their original names exactly — no automatic .txt suffixes. Characters without an IKEMEN movelist are given a best-effort command list generated from their .cmd file. Stage packages are registered under [ExtraStages], with bundled-music handling when possible.',
    1,
)

old_install = '''        try {\n            copyLocalDirExact(sourceDir, target);\n            String entry = targetName + "/" + def.getName();\n            addCharacterRosterEntries(g, Arrays.asList(entry));\n            return entry;\n        } catch (Exception e) {'''
new_install = '''        try {\n            MovelistResult movelist = ensureAutoMovelistLocal(sourceDir, def);\n            copyLocalDirExact(sourceDir, target);\n            String entry = targetName + "/" + def.getName();\n            addCharacterRosterEntries(g, Arrays.asList(entry));\n            if (movelist.generated) return entry + "  [auto command list: " + movelist.commands + " commands]";\n            return entry;\n        } catch (Exception e) {'''
if old_install not in text:
    raise SystemExit('character install insertion point not found')
text = text.replace(old_install, new_install, 1)

insert_before = '    private void repairExistingCharacters() {'
if insert_before not in text:
    raise SystemExit('helper insertion point not found')

helpers = r'''    private MovelistResult ensureAutoMovelistLocal(File sourceDir, File def) throws IOException {
        String defText = readLocalLatin1(def, 1024 * 1024);
        String configured = unquote(iniValue(defText, "Files", "movelist"));
        if (!configured.isBlank()) {
            File existing = resolveLocalReference(sourceDir, configured);
            if (existing != null && existing.isFile()) return new MovelistResult(false, 0);
        }

        String cmdRef = unquote(iniValue(defText, "Files", "cmd"));
        if (cmdRef.isBlank()) return new MovelistResult(false, 0);
        File cmd = resolveLocalReference(sourceDir, cmdRef);
        if (cmd == null || !cmd.isFile()) return new MovelistResult(false, 0);

        List<CommandEntry> commands = parseCmdCommands(readLocalLatin1(cmd, 2 * 1024 * 1024));
        if (commands.isEmpty()) return new MovelistResult(false, 0);

        String moveName = uniqueLocalFileName(sourceDir, "ikemen_auto_movelist.dat");
        File moveFile = new File(sourceDir, moveName);
        Files.write(moveFile.toPath(), buildGeneratedMovelist(commands).getBytes(StandardCharsets.UTF_8));
        String updatedDef = setIniValue(defText, "Files", "movelist", moveName);
        Files.write(def.toPath(), updatedDef.getBytes(StandardCharsets.ISO_8859_1));
        return new MovelistResult(true, commands.size());
    }

    private MovelistResult ensureAutoMovelistSaf(DocumentFile characterRoot, SafDefPick pick) throws IOException {
        String parentRel = parentPath(pick.relativePath);
        DocumentFile baseDir = parentRel.isEmpty() ? characterRoot : path(characterRoot, parentRel);
        if (baseDir == null || !baseDir.isDirectory()) return new MovelistResult(false, 0);

        String defText = readSafLatin1(pick.file, 1024 * 1024);
        String configured = unquote(iniValue(defText, "Files", "movelist"));
        if (!configured.isBlank()) {
            DocumentFile existing = resolveSafReference(baseDir, configured);
            if (existing != null && existing.isFile()) return new MovelistResult(false, 0);
        }

        String cmdRef = unquote(iniValue(defText, "Files", "cmd"));
        if (cmdRef.isBlank()) return new MovelistResult(false, 0);
        DocumentFile cmd = resolveSafReference(baseDir, cmdRef);
        if (cmd == null || !cmd.isFile()) return new MovelistResult(false, 0);

        List<CommandEntry> commands = parseCmdCommands(readSafLatin1(cmd, 2 * 1024 * 1024));
        if (commands.isEmpty()) return new MovelistResult(false, 0);

        String moveName = uniqueSafFileName(baseDir, "ikemen_auto_movelist.dat");
        DocumentFile moveFile = createExactFile(baseDir, moveName);
        try (OutputStream out = getContentResolver().openOutputStream(moveFile.getUri(), "w")) {
            if (out == null) throw new IOException("Could not write generated command list.");
            out.write(buildGeneratedMovelist(commands).getBytes(StandardCharsets.UTF_8));
        }
        String updatedDef = setIniValue(defText, "Files", "movelist", moveName);
        writeSafLatin1(pick.file, updatedDef);
        return new MovelistResult(true, commands.size());
    }

    private void generateMissingMovelists() {
        busy("Generating missing command lists…");
        worker.execute(() -> {
            try {
                GameFiles g = resolveGameFiles();
                int detected = 0;
                int generated = 0;
                int commandCount = 0;
                int skipped = 0;
                int failed = 0;
                List<String> failures = new ArrayList<>();

                for (DocumentFile dir : g.charsDir.listFiles()) {
                    if (!dir.isDirectory() || dir.getName() == null) continue;
                    SafDefPick def = findBestCharacterDefSaf(dir);
                    if (def == null) continue;
                    detected++;
                    try {
                        MovelistResult result = ensureAutoMovelistSaf(dir, def);
                        if (result.generated) {
                            generated++;
                            commandCount += result.commands;
                        } else {
                            skipped++;
                        }
                    } catch (Exception e) {
                        failed++;
                        if (failures.size() < 5) failures.add(dir.getName() + ": " + message(e));
                    }
                }

                StringBuilder out = new StringBuilder();
                out.append("Command-list scan complete ✓")
                        .append("\n\nDetected characters: ").append(detected)
                        .append("\nGenerated lists: ").append(generated)
                        .append("\nCommands added: ").append(commandCount)
                        .append("\nAlready had a list / no usable CMD: ").append(skipped)
                        .append("\nFailed: ").append(failed);
                for (String failure : failures) out.append("\n• ").append(failure);
                success(out.toString());
            } catch (Exception e) {
                fail("Command-list generation failed.\n\n" + message(e));
            }
        });
    }

    private List<CommandEntry> parseCmdCommands(String text) {
        List<CommandEntry> all = new ArrayList<>();
        boolean inCommand = false;
        String name = null;
        String command = null;

        for (String raw : text.split("\\r?\\n")) {
            String line = stripComment(raw).trim();
            if (line.isEmpty()) continue;
            if (line.startsWith("[") && line.endsWith("]")) {
                if (inCommand) addParsedCommand(all, name, command);
                inCommand = line.substring(1, line.length() - 1).trim().equalsIgnoreCase("Command");
                name = null;
                command = null;
                continue;
            }
            if (!inCommand) continue;
            int eq = line.indexOf('=');
            if (eq < 0) continue;
            String key = line.substring(0, eq).trim();
            String value = unquote(line.substring(eq + 1).trim());
            if (key.equalsIgnoreCase("name")) name = value;
            else if (key.equalsIgnoreCase("command")) command = value;
        }
        if (inCommand) addParsedCommand(all, name, command);

        List<CommandEntry> useful = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        for (CommandEntry e : all) {
            if (isNoiseCommand(e.name, e.command)) continue;
            boolean interesting = e.command.contains(",") || e.command.contains("+") || e.command.contains("~")
                    || e.command.contains("/") || e.command.contains("$") || e.command.contains(">");
            if (!interesting) continue;
            String key = e.name.toLowerCase(Locale.ROOT) + "\n" + e.command.toLowerCase(Locale.ROOT);
            if (seen.add(key)) useful.add(e);
            if (useful.size() >= 100) break;
        }

        if (useful.isEmpty()) {
            for (CommandEntry e : all) {
                if (isNoiseCommand(e.name, e.command)) continue;
                String key = e.name.toLowerCase(Locale.ROOT) + "\n" + e.command.toLowerCase(Locale.ROOT);
                if (seen.add(key)) useful.add(e);
                if (useful.size() >= 60) break;
            }
        }
        return useful;
    }

    private static void addParsedCommand(List<CommandEntry> out, String name, String command) {
        if (name == null || command == null) return;
        name = name.trim();
        command = command.trim();
        if (!name.isEmpty() && !command.isEmpty()) out.add(new CommandEntry(name, command));
    }

    private static boolean isNoiseCommand(String name, String command) {
        String n = name.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]", "");
        if (n.isEmpty()) return true;
        if (n.matches("ai\\d*") || n.matches("cpu\\d*") || n.startsWith("aicommand")) return true;
        if (n.startsWith("hold") || n.equals("recovery") || n.equals("fwd") || n.equals("back")
                || n.equals("up") || n.equals("down")) return true;
        String c = command.replaceAll("\\s+", "").toLowerCase(Locale.ROOT);
        return c.equals("f") || c.equals("b") || c.equals("u") || c.equals("d")
                || c.equals("df") || c.equals("db") || c.equals("uf") || c.equals("ub");
    }

    private static String buildGeneratedMovelist(List<CommandEntry> commands) {
        StringBuilder out = new StringBuilder();
        out.append("AUTO-GENERATED COMMAND LIST\n");
        out.append("Generated from this character's MUGEN .cmd file. Names and inputs may be imperfect.\n\n");
        for (CommandEntry e : commands) {
            String name = e.name.replace('_', ' ').replace('<', '[').replace('>', ']').trim().replaceAll("\\s+", " ");
            String command = e.command.replace('<', '[').replace('>', ']').trim()
                    .replaceAll("\\s*,\\s*", ", ")
                    .replaceAll("\\s*\\+\\s*", " + ");
            out.append(name).append("\t\t").append(command).append('\n');
        }
        return out.toString();
    }

    private File resolveLocalReference(File baseDir, String reference) throws IOException {
        String clean = cleanPath(unquote(reference));
        if (clean.isEmpty() || clean.contains("..")) return null;
        File direct = new File(baseDir, clean);
        String baseCanonical = baseDir.getCanonicalPath() + File.separator;
        String directCanonical = direct.getCanonicalPath();
        if (directCanonical.startsWith(baseCanonical) && direct.isFile()) return direct;
        return findLocalByName(baseDir, new File(clean).getName());
    }

    private File findLocalByName(File dir, String name) {
        File[] files = dir.listFiles();
        if (files == null) return null;
        for (File f : files) if (f.isFile() && f.getName().equalsIgnoreCase(name)) return f;
        for (File f : files) {
            if (!f.isDirectory()) continue;
            File found = findLocalByName(f, name);
            if (found != null) return found;
        }
        return null;
    }

    private DocumentFile resolveSafReference(DocumentFile baseDir, String reference) {
        String clean = cleanPath(unquote(reference));
        if (clean.isEmpty() || clean.contains("..")) return null;
        DocumentFile direct = path(baseDir, clean);
        if (direct != null && direct.isFile()) return direct;
        String base = clean.substring(clean.lastIndexOf('/') + 1);
        return findSafByName(baseDir, base);
    }

    private DocumentFile findSafByName(DocumentFile dir, String name) {
        for (DocumentFile f : dir.listFiles()) {
            if (f.isFile() && f.getName() != null && f.getName().equalsIgnoreCase(name)) return f;
        }
        for (DocumentFile f : dir.listFiles()) {
            if (!f.isDirectory()) continue;
            DocumentFile found = findSafByName(f, name);
            if (found != null) return found;
        }
        return null;
    }

    private String uniqueLocalFileName(File parent, String wanted) {
        if (!new File(parent, wanted).exists()) return wanted;
        String base = stripExtension(wanted);
        String ext = wanted.substring(base.length());
        int n = 2;
        String candidate;
        do candidate = base + "_" + n++ + ext; while (new File(parent, candidate).exists());
        return candidate;
    }

    private String uniqueSafFileName(DocumentFile parent, String wanted) {
        if (childExact(parent, wanted) == null) return wanted;
        String base = stripExtension(wanted);
        String ext = wanted.substring(base.length());
        int n = 2;
        String candidate;
        do candidate = base + "_" + n++ + ext; while (childExact(parent, candidate) != null);
        return candidate;
    }

    private String readSafLatin1(DocumentFile file, int maxBytes) throws IOException {
        try (InputStream in = getContentResolver().openInputStream(file.getUri())) {
            if (in == null) throw new IOException("Could not read " + file.getName());
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int remaining = maxBytes;
            while (remaining > 0) {
                int n = in.read(buf, 0, Math.min(buf.length, remaining));
                if (n < 0) break;
                out.write(buf, 0, n);
                remaining -= n;
            }
            return out.toString(StandardCharsets.ISO_8859_1);
        }
    }

    private void writeSafLatin1(DocumentFile file, String text) throws IOException {
        try (OutputStream out = getContentResolver().openOutputStream(file.getUri(), "wt")) {
            if (out == null) throw new IOException("Could not write " + file.getName());
            out.write(text.getBytes(StandardCharsets.ISO_8859_1));
        }
    }

'''
text = text.replace(insert_before, helpers + insert_before, 1)

inner_marker = '    private static class DefPick {'
inner_classes = '''    private static class CommandEntry {\n        final String name;\n        final String command;\n        CommandEntry(String name, String command) { this.name = name; this.command = command; }\n    }\n\n    private static class MovelistResult {\n        final boolean generated;\n        final int commands;\n        MovelistResult(boolean generated, int commands) { this.generated = generated; this.commands = commands; }\n    }\n\n'''
if inner_marker not in text:
    raise SystemExit('inner class insertion point not found')
text = text.replace(inner_marker, inner_classes + inner_marker, 1)

dst.write_text(text, encoding='utf-8')
print(f'Wrote {dst} ({len(text)} bytes)')
