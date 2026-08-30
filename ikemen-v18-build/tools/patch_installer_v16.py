from pathlib import Path

src = Path('app/src/main/java/com/narmanb/ikemeninstaller/InstallerActivityV15.java')
dst = Path('app/src/main/java/com/narmanb/ikemeninstaller/InstallerActivityV16.java')
text = src.read_text(encoding='utf-8')

text = text.replace('public class InstallerActivityV15 extends Activity {', 'public class InstallerActivityV16 extends Activity {', 1)
text = text.replace(
    'v1.5 — exact filename preservation, single/multiple character and stage installs, plus automatic IKEMEN command-list generation from MUGEN .cmd files.',
    'v1.6 — improved automatic command lists with IKEMEN direction/button glyphs, categories, and update support for previously generated lists.',
    1,
)
text = text.replace('Generate missing command lists', 'Generate/update command lists', 1)
text = text.replace(
    'Characters without an IKEMEN movelist are given a best-effort command list generated from their .cmd file.',
    'Characters without an IKEMEN movelist are given a best-effort command list generated from their .cmd file using IKEMEN glyphs and categories.',
    1,
)

local_start = text.index('    private MovelistResult ensureAutoMovelistLocal(')
local_end = text.index('    private MovelistResult ensureAutoMovelistSaf(', local_start)
new_local = r'''    private MovelistResult ensureAutoMovelistLocal(File sourceDir, File def) throws IOException {
        String defText = readLocalLatin1(def, 1024 * 1024);
        String configured = unquote(iniValue(defText, "Files", "movelist"));
        File existingAuto = null;
        if (!configured.isBlank()) {
            File existing = resolveLocalReference(sourceDir, configured);
            if (existing != null && existing.isFile()) {
                if (!isAutoMovelistName(configured)) return new MovelistResult(false, 0);
                existingAuto = existing;
            }
        }

        String cmdRef = unquote(iniValue(defText, "Files", "cmd"));
        if (cmdRef.isBlank()) return new MovelistResult(false, 0);
        File cmd = resolveLocalReference(sourceDir, cmdRef);
        if (cmd == null || !cmd.isFile()) return new MovelistResult(false, 0);

        List<CommandEntry> commands = parseCmdCommands(readLocalLatin1(cmd, 2 * 1024 * 1024));
        if (commands.isEmpty()) return new MovelistResult(false, 0);

        String moveName = existingAuto != null ? existingAuto.getName() : uniqueLocalFileName(sourceDir, "ikemen_auto_movelist.dat");
        File moveFile = existingAuto != null ? existingAuto : new File(sourceDir, moveName);
        Files.write(moveFile.toPath(), buildGeneratedMovelist(commands).getBytes(StandardCharsets.UTF_8));
        String updatedDef = setIniValue(defText, "Files", "movelist", moveName);
        Files.write(def.toPath(), updatedDef.getBytes(StandardCharsets.ISO_8859_1));
        return new MovelistResult(true, commands.size());
    }

'''
text = text[:local_start] + new_local + text[local_end:]

saf_start = text.index('    private MovelistResult ensureAutoMovelistSaf(')
saf_end = text.index('    private void generateMissingMovelists()', saf_start)
new_saf = r'''    private MovelistResult ensureAutoMovelistSaf(DocumentFile characterRoot, SafDefPick pick) throws IOException {
        String parentRel = parentPath(pick.relativePath);
        DocumentFile baseDir = parentRel.isEmpty() ? characterRoot : path(characterRoot, parentRel);
        if (baseDir == null || !baseDir.isDirectory()) return new MovelistResult(false, 0);

        String defText = readSafLatin1(pick.file, 1024 * 1024);
        String configured = unquote(iniValue(defText, "Files", "movelist"));
        DocumentFile existingAuto = null;
        if (!configured.isBlank()) {
            DocumentFile existing = resolveSafReference(baseDir, configured);
            if (existing != null && existing.isFile()) {
                if (!isAutoMovelistName(configured)) return new MovelistResult(false, 0);
                existingAuto = existing;
            }
        }

        String cmdRef = unquote(iniValue(defText, "Files", "cmd"));
        if (cmdRef.isBlank()) return new MovelistResult(false, 0);
        DocumentFile cmd = resolveSafReference(baseDir, cmdRef);
        if (cmd == null || !cmd.isFile()) return new MovelistResult(false, 0);

        List<CommandEntry> commands = parseCmdCommands(readSafLatin1(cmd, 2 * 1024 * 1024));
        if (commands.isEmpty()) return new MovelistResult(false, 0);

        String moveName = existingAuto != null && existingAuto.getName() != null
                ? existingAuto.getName() : uniqueSafFileName(baseDir, "ikemen_auto_movelist.dat");
        DocumentFile moveFile = existingAuto != null ? existingAuto : createExactFile(baseDir, moveName);
        try (OutputStream out = getContentResolver().openOutputStream(moveFile.getUri(), "w")) {
            if (out == null) throw new IOException("Could not write generated command list.");
            out.write(buildGeneratedMovelist(commands).getBytes(StandardCharsets.UTF_8));
        }
        String updatedDef = setIniValue(defText, "Files", "movelist", moveName);
        writeSafLatin1(pick.file, updatedDef);
        return new MovelistResult(true, commands.size());
    }

'''
text = text[:saf_start] + new_saf + text[saf_end:]

text = text.replace('Generating missing command lists…', 'Generating/updating command lists…')
text = text.replace('Command-list scan complete ✓', 'Command-list generation/update complete ✓')
text = text.replace('Generated lists: ', 'Generated/updated lists: ')
text = text.replace('Already had a list / no usable CMD: ', 'Hand-authored list / no usable CMD: ')

build_start = text.index('    private static String buildGeneratedMovelist(')
build_end = text.index('    private File resolveLocalReference(', build_start)
new_build = r'''    private static String buildGeneratedMovelist(List<CommandEntry> commands) {
        List<CommandEntry> unique = new ArrayList<>();
        List<CommandEntry> throwsList = new ArrayList<>();
        List<CommandEntry> specials = new ArrayList<>();
        List<CommandEntry> supers = new ArrayList<>();

        for (CommandEntry e : commands) {
            String category = commandCategory(e);
            if (category.equals("Throws")) throwsList.add(e);
            else if (category.equals("Special Moves")) specials.add(e);
            else if (category.equals("Super Moves")) supers.add(e);
            else unique.add(e);
        }

        StringBuilder out = new StringBuilder();
        appendMovelistCategory(out, "Unique Attacks", unique);
        appendMovelistCategory(out, "Throws", throwsList);
        appendMovelistCategory(out, "Special Moves", specials);
        appendMovelistCategory(out, "Super Moves", supers);
        return out.toString();
    }

    private static void appendMovelistCategory(StringBuilder out, String title, List<CommandEntry> entries) {
        if (entries.isEmpty()) return;
        if (out.length() > 0) out.append('\n');
        out.append("<#f0f000>:").append(title).append(":</>\n");
        for (CommandEntry e : entries) {
            String name = cleanMoveName(e.name);
            String glyphs = toIkemenGlyphCommand(e.command);
            if (glyphs.isBlank()) continue;
            out.append(name);
            int tabs = Math.max(2, 7 - name.length() / 6);
            for (int i = 0; i < tabs; i++) out.append('\t');
            out.append(glyphs).append('\n');
        }
    }

    private static String cleanMoveName(String value) {
        String name = value == null ? "Move" : value.replace('_', ' ').trim().replaceAll("\\s+", " ");
        name = name.replaceAll("(?i)\\bqcf\\b", "QCF")
                .replaceAll("(?i)\\bqcb\\b", "QCB")
                .replaceAll("(?i)\\bhcf\\b", "HCF")
                .replaceAll("(?i)\\bhcb\\b", "HCB")
                .replaceAll("(?i)\\bdp\\b", "DP");
        if (name.length() > 34) name = name.substring(0, 31) + "...";
        return name;
    }

    private static String commandCategory(CommandEntry e) {
        String n = e.name == null ? "" : e.name.toLowerCase(Locale.ROOT).replace('_', ' ');
        if (containsAny(n, "throw", "grab", "toss", "grapple")) return "Throws";
        if (containsAny(n, "super", "hyper", "ultra", "ultimate", "desperation", "finisher", "level 2", "level 3", "lvl2", "lvl3", "max")) {
            return "Super Moves";
        }
        int dirs = countDirectionInputs(e.command);
        if (dirs >= 2 || containsAny(n, "qcf", "qcb", "hcf", "hcb", "dp", "special", "fireball", "projectile")) {
            return "Special Moves";
        }
        return "Unique Attacks";
    }

    private static boolean containsAny(String value, String... needles) {
        for (String needle : needles) if (value.contains(needle)) return true;
        return false;
    }

    private static int countDirectionInputs(String command) {
        int count = 0;
        for (String piece : command.split(",")) {
            for (String part : piece.split("\\+")) {
                if (isDirectionToken(cleanInputToken(part))) count++;
            }
        }
        return count;
    }

    private static String toIkemenGlyphCommand(String command) {
        List<String> dirs = new ArrayList<>();
        List<Boolean> charges = new ArrayList<>();
        List<String> buttons = new ArrayList<>();

        for (String piece : command.split(",")) {
            for (String part : piece.split("\\+")) {
                String raw = part.trim();
                if (raw.isEmpty()) continue;
                boolean charged = raw.matches(".*~\\s*\\d+.*");
                String token = cleanInputToken(raw);
                if (isDirectionToken(token)) {
                    dirs.add(token);
                    charges.add(charged);
                } else {
                    String button = buttonGlyph(token);
                    if (!button.isEmpty()) buttons.add(button);
                }
            }
        }

        String motion = buildDirectionGlyphs(dirs, charges);
        String buttonText = String.join("+", buttons);
        if (motion.isEmpty()) return buttonText;
        if (buttonText.isEmpty()) return motion;
        if (dirs.size() == 1 && !charges.get(0)) return motion + "_+" + buttonText;
        return motion + buttonText;
    }

    private static String cleanInputToken(String raw) {
        String token = raw.trim().toUpperCase(Locale.ROOT);
        token = token.replaceAll("~\\s*\\d*", "")
                .replace("$", "")
                .replace("/", "")
                .replace(">", "")
                .replace("<", "")
                .replace(" ", "");
        token = token.replaceAll("^\\d+", "");
        return token;
    }

    private static boolean isDirectionToken(String token) {
        return token.equals("D") || token.equals("U") || token.equals("B") || token.equals("F")
                || token.equals("DB") || token.equals("DF") || token.equals("UB") || token.equals("UF");
    }

    private static String buttonGlyph(String token) {
        switch (token) {
            case "X": case "Y": case "Z": case "A": case "B": case "C": case "S":
                return "^" + token;
            case "P": return "^P";
            case "K": return "^K";
            default: return "";
        }
    }

    private static String buildDirectionGlyphs(List<String> dirs, List<Boolean> charges) {
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < dirs.size();) {
            if (charges.get(i)) {
                out.append('~').append(dirs.get(i));
                i++;
                continue;
            }
            if (i + 2 < dirs.size() && !charges.get(i + 1) && !charges.get(i + 2)) {
                String a = dirs.get(i), b = dirs.get(i + 1), c = dirs.get(i + 2);
                if (a.equals("D") && b.equals("DF") && c.equals("F")) { out.append("_QDF"); i += 3; continue; }
                if (a.equals("D") && b.equals("DB") && c.equals("B")) { out.append("_QDB"); i += 3; continue; }
                if (a.equals("F") && b.equals("D") && c.equals("DF")) { out.append("_DSF"); i += 3; continue; }
                if (a.equals("B") && b.equals("D") && c.equals("DB")) { out.append("_DSB"); i += 3; continue; }
            }
            if (i + 1 < dirs.size() && !charges.get(i + 1)) {
                if (dirs.get(i).equals("F") && dirs.get(i + 1).equals("F")) { out.append("_XFF"); i += 2; continue; }
                if (dirs.get(i).equals("B") && dirs.get(i + 1).equals("B")) { out.append("_XBB"); i += 2; continue; }
            }
            out.append('_').append(dirs.get(i));
            i++;
        }
        return out.toString();
    }

    private static boolean isAutoMovelistName(String value) {
        String clean = cleanPath(unquote(value));
        int slash = clean.lastIndexOf('/');
        String base = slash >= 0 ? clean.substring(slash + 1) : clean;
        String lower = base.toLowerCase(Locale.ROOT);
        return lower.startsWith("ikemen_auto_movelist") && lower.endsWith(".dat");
    }

'''
text = text[:build_start] + new_build + text[build_end:]

dst.write_text(text, encoding='utf-8')
print(f'Wrote {dst} ({len(text)} bytes)')
