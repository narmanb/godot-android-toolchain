from pathlib import Path

src = Path('app/src/main/java/com/narmanb/ikemeninstaller/InstallerActivityV16.java')
dst = Path('app/src/main/java/com/narmanb/ikemeninstaller/InstallerActivityV17.java')
text = src.read_text(encoding='utf-8')

text = text.replace('public class InstallerActivityV16 extends Activity {', 'public class InstallerActivityV17 extends Activity {', 1)
text = text.replace(
    'v1.6 — improved automatic command lists with IKEMEN direction/button glyphs, categories, and update support for previously generated lists.',
    'v1.7 — keeps every v1.6 feature and adds a separate deep scan for already-installed characters that traces State -1 command usage to find moves the basic generator can miss.',
    1,
)

# Imports used only by the deep scanner.
text = text.replace('import java.util.Locale;\n', 'import java.util.Locale;\nimport java.util.LinkedHashMap;\nimport java.util.Map;\nimport java.util.regex.Matcher;\nimport java.util.regex.Pattern;\n', 1)

# Keep the normal generator exactly as its own option, and add a second, explicitly deeper pass.
old_ui = '''        Button movelistRepair = button("Generate/update command lists", true);\n        movelistRepair.setOnClickListener(v -> generateMissingMovelists());\n        root.addView(movelistRepair);\n\n        addHeading(root, "Stages");'''
new_ui = '''        Button movelistRepair = button("Generate/update command lists", true);\n        movelistRepair.setOnClickListener(v -> generateMissingMovelists());\n        root.addView(movelistRepair);\n\n        Button deepMovelistRepair = button("Deep-scan installed command lists", true);\n        deepMovelistRepair.setOnClickListener(v -> deepScanInstalledMovelists());\n        root.addView(deepMovelistRepair);\n\n        addHeading(root, "Stages");'''
if old_ui not in text:
    raise SystemExit('v1.7 UI insertion point not found')
text = text.replace(old_ui, new_ui, 1)

# Make the existing glyph converter preserve lowercase MUGEN button letters (notably b)
# instead of accidentally turning them into directional B, and render bare ~D style releases
# with IKEMEN's hold/release direction glyph rather than a plain arrow.
text = text.replace('boolean charged = raw.matches(".*~\\\\s*\\\\d+.*");', 'boolean charged = raw.contains("~");', 1)

old_clean = '''    private static String cleanInputToken(String raw) {\n        String token = raw.trim().toUpperCase(Locale.ROOT);\n        token = token.replaceAll("~\\\\s*\\\\d*", "")\n                .replace("$", "")\n                .replace("/", "")\n                .replace(">", "")\n                .replace("<", "")\n                .replace(" ", "");\n        token = token.replaceAll("^\\\\d+", "");\n        return token;\n    }'''
new_clean = '''    private static String cleanInputToken(String raw) {\n        String token = raw.trim();\n        token = token.replaceAll("~\\\\s*\\\\d*", "")\n                .replace("$", "")\n                .replace("/", "")\n                .replace(">", "")\n                .replace("<", "")\n                .replace(" ", "");\n        token = token.replaceAll("^\\\\d+", "");\n        return token;\n    }'''
if old_clean not in text:
    raise SystemExit('cleanInputToken block not found')
text = text.replace(old_clean, new_clean, 1)

old_button = '''    private static String buttonGlyph(String token) {\n        switch (token) {\n            case "X": case "Y": case "Z": case "A": case "B": case "C": case "S":\n                return "^" + token;\n            case "P": return "^P";\n            case "K": return "^K";\n            default: return "";\n        }\n    }'''
new_button = '''    private static String buttonGlyph(String token) {\n        switch (token) {\n            case "x": case "X": return "^X";\n            case "y": case "Y": return "^Y";\n            case "z": case "Z": return "^Z";\n            case "a": case "A": return "^A";\n            case "b": return "^B";\n            case "c": case "C": return "^C";\n            case "s": case "S": return "^S";\n            case "P": case "p": return "^P";\n            case "K": case "k": return "^K";\n            default: return "";\n        }\n    }'''
if old_button not in text:
    raise SystemExit('buttonGlyph block not found')
text = text.replace(old_button, new_button, 1)

# Deep scan implementation. It only writes our ikemen_auto_movelist*.dat files (or creates one
# when there is no movelist); an existing hand-authored movelist is deliberately left untouched.
insert_before = '    private void repairExistingCharacters() {'
if insert_before not in text:
    raise SystemExit('deep scan insertion point not found')

helpers = r'''    private void deepScanInstalledMovelists() {
        busy("Deep-scanning installed characters…");
        worker.execute(() -> {
            try {
                GameFiles g = resolveGameFiles();
                int detected = 0;
                int rebuilt = 0;
                int moves = 0;
                int handAuthored = 0;
                int noData = 0;
                int failed = 0;
                List<String> failures = new ArrayList<>();

                for (DocumentFile dir : g.charsDir.listFiles()) {
                    if (!dir.isDirectory() || dir.getName() == null) continue;
                    SafDefPick def = findBestCharacterDefSaf(dir);
                    if (def == null) continue;
                    detected++;
                    try {
                        DeepScanResult result = deepRebuildMovelistSaf(dir, def);
                        if (result.status == DeepScanResult.REBUILT) {
                            rebuilt++;
                            moves += result.moves;
                        } else if (result.status == DeepScanResult.HAND_AUTHORED) {
                            handAuthored++;
                        } else {
                            noData++;
                        }
                    } catch (Exception e) {
                        failed++;
                        if (failures.size() < 6) failures.add(dir.getName() + ": " + message(e));
                    }
                }

                StringBuilder out = new StringBuilder();
                out.append("Deep command-list scan complete ✓")
                        .append("\n\nDetected characters: ").append(detected)
                        .append("\nAuto lists rebuilt: ").append(rebuilt)
                        .append("\nMoves listed: ").append(moves)
                        .append("\nHand-authored lists preserved: ").append(handAuthored)
                        .append("\nNo usable command data: ").append(noData)
                        .append("\nFailed: ").append(failed);
                for (String failure : failures) out.append("\n• ").append(failure);
                success(out.toString());
            } catch (Exception e) {
                fail("Deep command-list scan failed.\n\n" + message(e));
            }
        });
    }

    private DeepScanResult deepRebuildMovelistSaf(DocumentFile characterRoot, SafDefPick pick) throws IOException {
        String parentRel = parentPath(pick.relativePath);
        DocumentFile baseDir = parentRel.isEmpty() ? characterRoot : path(characterRoot, parentRel);
        if (baseDir == null || !baseDir.isDirectory()) return new DeepScanResult(DeepScanResult.NO_DATA, 0);

        String defText = readSafLatin1(pick.file, 1024 * 1024);
        String configured = unquote(iniValue(defText, "Files", "movelist"));
        DocumentFile existingAuto = null;
        if (!configured.isBlank()) {
            DocumentFile existing = resolveSafReference(baseDir, configured);
            if (existing != null && existing.isFile()) {
                if (!isAutoMovelistName(configured)) {
                    return new DeepScanResult(DeepScanResult.HAND_AUTHORED, 0);
                }
                existingAuto = existing;
            }
        }

        String cmdRef = unquote(iniValue(defText, "Files", "cmd"));
        if (cmdRef.isBlank()) return new DeepScanResult(DeepScanResult.NO_DATA, 0);
        DocumentFile cmd = resolveSafReference(baseDir, cmdRef);
        if (cmd == null || !cmd.isFile()) return new DeepScanResult(DeepScanResult.NO_DATA, 0);

        String cmdText = readSafLatin1(cmd, 3 * 1024 * 1024);
        List<CommandEntry> allCommands = parseAllCmdCommands(cmdText);
        if (allCommands.isEmpty()) return new DeepScanResult(DeepScanResult.NO_DATA, 0);

        Map<String, CommandEntry> commandByName = new LinkedHashMap<>();
        for (CommandEntry e : allCommands) commandByName.putIfAbsent(e.name.toLowerCase(Locale.ROOT), e);

        Map<String, DeepHint> hints = new LinkedHashMap<>();
        List<DocumentFile> logicFiles = new ArrayList<>();
        collectLogicFiles(characterRoot, logicFiles, 0);
        for (DocumentFile logic : logicFiles) {
            try {
                collectDeepHintsFromText(readSafLatin1(logic, 2 * 1024 * 1024), hints);
            } catch (Exception ignored) {
                // One odd legacy text file should not prevent scanning the rest of the character.
            }
        }

        List<DeepMove> deepMoves = new ArrayList<>();
        Set<String> included = new HashSet<>();

        // First: commands actually referenced by State -1 player-control logic.
        for (Map.Entry<String, DeepHint> entry : hints.entrySet()) {
            CommandEntry command = commandByName.get(entry.getKey());
            if (command == null || isNoiseCommand(command.name, command.command)) continue;
            DeepHint hint = entry.getValue();
            String display = hint.displayName == null || hint.displayName.isBlank()
                    ? cleanMoveName(command.name) : hint.displayName;
            String category = hint.category == null ? commandCategory(command) : hint.category;
            deepMoves.add(new DeepMove(display, command.command, category));
            included.add(entry.getKey());
        }

        // Second: retain everything the normal v1.6 generator already considered useful.
        for (CommandEntry command : parseCmdCommands(cmdText)) {
            String key = command.name.toLowerCase(Locale.ROOT);
            if (included.add(key)) deepMoves.add(new DeepMove(cleanMoveName(command.name), command.command, commandCategory(command)));
        }

        // If state tracing found nothing useful, fall back to all non-noise command definitions rather
        // than producing a worse/empty list. Cap keeps pathological AI-heavy CMD files manageable.
        if (deepMoves.isEmpty()) {
            for (CommandEntry command : allCommands) {
                if (isNoiseCommand(command.name, command.command)) continue;
                String key = command.name.toLowerCase(Locale.ROOT);
                if (!included.add(key)) continue;
                deepMoves.add(new DeepMove(cleanMoveName(command.name), command.command, commandCategory(command)));
                if (deepMoves.size() >= 120) break;
            }
        }

        if (deepMoves.isEmpty()) return new DeepScanResult(DeepScanResult.NO_DATA, 0);

        String moveName = existingAuto != null && existingAuto.getName() != null
                ? existingAuto.getName() : uniqueSafFileName(baseDir, "ikemen_auto_movelist.dat");
        DocumentFile moveFile = existingAuto != null ? existingAuto : createExactFile(baseDir, moveName);
        try (OutputStream out = getContentResolver().openOutputStream(moveFile.getUri(), "w")) {
            if (out == null) throw new IOException("Could not write deep-generated command list.");
            out.write(buildDeepGeneratedMovelist(deepMoves).getBytes(StandardCharsets.UTF_8));
        }
        String updatedDef = setIniValue(defText, "Files", "movelist", moveName);
        writeSafLatin1(pick.file, updatedDef);
        return new DeepScanResult(DeepScanResult.REBUILT, deepMoves.size());
    }

    private List<CommandEntry> parseAllCmdCommands(String text) {
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
        return all;
    }

    private void collectLogicFiles(DocumentFile dir, List<DocumentFile> out, int depth) {
        if (depth > 6 || out.size() >= 120) return;
        for (DocumentFile f : dir.listFiles()) {
            if (out.size() >= 120) return;
            if (f.isDirectory()) {
                collectLogicFiles(f, out, depth + 1);
                continue;
            }
            String name = f.getName();
            if (name == null) continue;
            String lower = name.toLowerCase(Locale.ROOT);
            if (lower.endsWith(".cmd") || lower.endsWith(".cns") || lower.endsWith(".st") || lower.endsWith(".zss")) {
                out.add(f);
            }
        }
    }

    private static void collectDeepHintsFromText(String text, Map<String, DeepHint> hints) {
        String header = null;
        StringBuilder block = new StringBuilder();
        for (String raw : text.split("\\r?\\n")) {
            String line = stripComment(raw).trim();
            if (line.startsWith("[") && line.endsWith("]")) {
                processStateMinusOneBlock(header, block.toString(), hints);
                header = line.substring(1, line.length() - 1).trim();
                block.setLength(0);
            } else if (header != null) {
                block.append(line).append('\n');
            }
        }
        processStateMinusOneBlock(header, block.toString(), hints);
    }

    private static void processStateMinusOneBlock(String header, String body, Map<String, DeepHint> hints) {
        if (header == null) return;
        String h = header.toLowerCase(Locale.ROOT).replace(" ", "");
        if (!h.startsWith("state-1,")) return;

        String display = header.substring(header.indexOf(',') + 1).trim();
        if (display.matches("[-+]?\\d+") || display.equalsIgnoreCase("changestate") || display.equalsIgnoreCase("state")) display = "";
        display = cleanMoveName(display);

        String category = inferDeepCategory(header, body);
        Matcher quoted = Pattern.compile("(?i)\\bcommand\\s*=\\s*\"([^\"]+)\"").matcher(body);
        while (quoted.find()) {
            putDeepHint(hints, quoted.group(1), display, category);
        }
        Matcher bare = Pattern.compile("(?i)\\bcommand\\s*=\\s*([A-Za-z0-9_ .+\\-]+)").matcher(body);
        while (bare.find()) {
            String value = bare.group(1).trim();
            if (!value.isEmpty() && !value.contains("=")) putDeepHint(hints, value, display, category);
        }
    }

    private static void putDeepHint(Map<String, DeepHint> hints, String commandName, String display, String category) {
        String clean = unquote(commandName).trim();
        if (clean.isEmpty()) return;
        String key = clean.toLowerCase(Locale.ROOT);
        DeepHint old = hints.get(key);
        DeepHint candidate = new DeepHint(display, category);
        if (old == null || categoryPriority(candidate.category) > categoryPriority(old.category)
                || (old.displayName == null || old.displayName.isBlank()) && display != null && !display.isBlank()) {
            hints.put(key, candidate);
        }
    }

    private static int categoryPriority(String value) {
        if ("Super Moves".equals(value)) return 3;
        if ("Throws".equals(value)) return 2;
        if ("Special Moves".equals(value)) return 1;
        return 0;
    }

    private static String inferDeepCategory(String header, String body) {
        String all = (header + "\n" + body).toLowerCase(Locale.ROOT);
        if (containsAny(all, "throw", "grab", "toss", "grapple")) return "Throws";
        if (containsAny(all, "super", "hyper", "ultra", "ultimate", "desperation", "finisher", "level 3", "level3", "lvl3", "level 2", "level2", "lvl2")) {
            return "Super Moves";
        }
        Matcher power = Pattern.compile("(?i)\\bpower\\s*>?=\\s*(\\d+)").matcher(body);
        while (power.find()) {
            try {
                if (Integer.parseInt(power.group(1)) >= 1000) return "Super Moves";
            } catch (NumberFormatException ignored) {}
        }
        return "Special Moves";
    }

    private static String buildDeepGeneratedMovelist(List<DeepMove> moves) {
        StringBuilder out = new StringBuilder();
        appendDeepCategory(out, "Unique Attacks", moves);
        appendDeepCategory(out, "Throws", moves);
        appendDeepCategory(out, "Special Moves", moves);
        appendDeepCategory(out, "Super Moves", moves);
        return out.toString();
    }

    private static void appendDeepCategory(StringBuilder out, String category, List<DeepMove> moves) {
        boolean any = false;
        for (DeepMove move : moves) if (category.equals(move.category)) { any = true; break; }
        if (!any) return;
        if (out.length() > 0) out.append('\n');
        out.append("<#f0f000>:").append(category).append(":</>\n");
        for (DeepMove move : moves) {
            if (!category.equals(move.category)) continue;
            String name = cleanMoveName(move.name);
            String glyphs = toIkemenGlyphCommand(move.command);
            if (glyphs.isBlank()) continue;
            out.append(name);
            int tabs = Math.max(2, 7 - name.length() / 6);
            for (int i = 0; i < tabs; i++) out.append('\t');
            out.append(glyphs).append('\n');
        }
    }

'''
text = text.replace(insert_before, helpers + insert_before, 1)

inner_marker = '    private static class CommandEntry {'
if inner_marker not in text:
    raise SystemExit('inner class insertion point not found')
inner_classes = '''    private static class DeepHint {\n        final String displayName;\n        final String category;\n        DeepHint(String displayName, String category) { this.displayName = displayName; this.category = category; }\n    }\n\n    private static class DeepMove {\n        final String name;\n        final String command;\n        final String category;\n        DeepMove(String name, String command, String category) { this.name = name; this.command = command; this.category = category; }\n    }\n\n    private static class DeepScanResult {\n        static final int REBUILT = 1;\n        static final int HAND_AUTHORED = 2;\n        static final int NO_DATA = 3;\n        final int status;\n        final int moves;\n        DeepScanResult(int status, int moves) { this.status = status; this.moves = moves; }\n    }\n\n'''
text = text.replace(inner_marker, inner_classes + inner_marker, 1)

dst.write_text(text, encoding='utf-8')
print(f'Wrote {dst} ({len(text)} bytes)')
