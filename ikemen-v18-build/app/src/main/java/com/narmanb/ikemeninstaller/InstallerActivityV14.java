package com.narmanb.ikemeninstaller;

import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
import android.database.Cursor;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.view.Gravity;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.documentfile.provider.DocumentFile;

import com.github.junrar.Junrar;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Date;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

public class InstallerActivityV14 extends Activity {
    private static final int REQ_GAME_FOLDER = 1001;
    private static final int REQ_CHAR_SINGLE = 1101;
    private static final int REQ_CHAR_MULTI = 1102;
    private static final int REQ_CHAR_FOLDER = 1103;
    private static final int REQ_STAGE_SINGLE = 1201;
    private static final int REQ_STAGE_MULTI = 1202;
    private static final int REQ_STAGE_FOLDER = 1203;

    private static final String PREFS = "ikemen_installer";
    private static final String KEY_GAME_URI = "game_uri";
    private static final Set<String> TEXT_EXTENSIONS = new HashSet<>(Arrays.asList(
            ".def", ".cmd", ".cns", ".air", ".st", ".zss", ".const"));
    private static final Set<String> AUDIO_EXTENSIONS = new HashSet<>(Arrays.asList(
            ".mp3", ".ogg", ".wav", ".mid", ".midi", ".mod", ".s3m", ".xm", ".it"));

    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final List<Button> actionButtons = new ArrayList<>();
    private Uri gameRootUri;
    private TextView folderView;
    private TextView statusView;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        String saved = getSharedPreferences(PREFS, MODE_PRIVATE).getString(KEY_GAME_URI, null);
        if (saved != null) gameRootUri = Uri.parse(saved);
        buildUi();
        refreshUi();
    }

    @Override
    protected void onDestroy() {
        worker.shutdownNow();
        super.onDestroy();
    }

    private void buildUi() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(18), dp(20), dp(18), dp(24));
        scroll.addView(root);

        TextView title = new TextView(this);
        title.setText("IKEMEN Content Installer");
        title.setTextSize(26);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        root.addView(title);

        TextView subtitle = new TextView(this);
        subtitle.setText("v1.4 — exact filename preservation, separate single/multiple character installs, and stage installation with bundled-music handling.");
        subtitle.setTextSize(15);
        subtitle.setPadding(0, dp(8), 0, dp(14));
        root.addView(subtitle);

        folderView = new TextView(this);
        folderView.setTextSize(13);
        folderView.setPadding(dp(10), dp(10), dp(10), dp(10));
        root.addView(folderView);

        Button choose = button("Choose IKEMEN game folder", false);
        choose.setOnClickListener(v -> chooseGameFolder());
        root.addView(choose);

        addHeading(root, "Characters");

        Button charSingle = button("Install ONE ZIP / RAR character", true);
        charSingle.setOnClickListener(v -> chooseArchive(false, REQ_CHAR_SINGLE));
        root.addView(charSingle);

        Button charMulti = button("Install MULTIPLE ZIP / RAR characters", true);
        charMulti.setOnClickListener(v -> chooseArchive(true, REQ_CHAR_MULTI));
        root.addView(charMulti);

        Button charFolder = button("Install unpacked character folder", true);
        charFolder.setOnClickListener(v -> chooseFolder(REQ_CHAR_FOLDER));
        root.addView(charFolder);

        Button charRepair = button("Repair/register characters already in chars/", true);
        charRepair.setOnClickListener(v -> repairExistingCharacters());
        root.addView(charRepair);

        addHeading(root, "Stages");

        Button stageSingle = button("Install ONE ZIP / RAR stage", true);
        stageSingle.setOnClickListener(v -> chooseArchive(false, REQ_STAGE_SINGLE));
        root.addView(stageSingle);

        Button stageMulti = button("Install MULTIPLE ZIP / RAR stages", true);
        stageMulti.setOnClickListener(v -> chooseArchive(true, REQ_STAGE_MULTI));
        root.addView(stageMulti);

        Button stageFolder = button("Install unpacked stage folder", true);
        stageFolder.setOnClickListener(v -> chooseFolder(REQ_STAGE_FOLDER));
        root.addView(stageFolder);

        Button stageRepair = button("Register stages already in stages/", true);
        stageRepair.setOnClickListener(v -> repairExistingStages());
        root.addView(stageRepair);

        TextView note = new TextView(this);
        note.setText("Files are copied with their original names exactly — no automatic .txt suffixes. Stage packages are registered under [ExtraStages]. If a package has a configured BGM, or exactly one bundled audio file with a blank BGM, the installer copies that audio into sound/ and points the stage to it.");
        note.setTextSize(13);
        note.setPadding(0, dp(14), 0, dp(8));
        root.addView(note);

        statusView = new TextView(this);
        statusView.setTypeface(Typeface.MONOSPACE);
        statusView.setTextSize(13);
        statusView.setPadding(dp(10), dp(10), dp(10), dp(10));
        statusView.setText("Ready.");
        root.addView(statusView);

        setContentView(scroll);
    }

    private void addHeading(LinearLayout root, String text) {
        TextView h = new TextView(this);
        h.setText(text);
        h.setTextSize(19);
        h.setTypeface(Typeface.DEFAULT_BOLD);
        h.setPadding(0, dp(16), 0, dp(4));
        root.addView(h);
    }

    private Button button(String text, boolean requiresRoot) {
        Button b = new Button(this);
        b.setText(text);
        b.setTextSize(15);
        b.setAllCaps(false);
        b.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, dp(4), 0, dp(4));
        b.setLayoutParams(lp);
        if (requiresRoot) actionButtons.add(b);
        return b;
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    private void refreshUi() {
        boolean ok = gameRootUri != null;
        folderView.setText(ok ? "IKEMEN folder selected ✓\n" + gameRootUri : "No IKEMEN folder selected.");
        for (Button b : actionButtons) b.setEnabled(ok);
    }

    private void busy(String text) {
        runOnUiThread(() -> {
            for (Button b : actionButtons) b.setEnabled(false);
            statusView.setText(text);
        });
    }

    private void success(String text) {
        runOnUiThread(() -> {
            refreshUi();
            statusView.setText(text);
        });
    }

    private void fail(String text) {
        runOnUiThread(() -> {
            refreshUi();
            statusView.setText("ERROR\n\n" + text);
        });
    }

    private void progress(String text) {
        runOnUiThread(() -> statusView.setText(text));
    }

    private void chooseGameFolder() {
        Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION
                | Intent.FLAG_GRANT_PREFIX_URI_PERMISSION);
        startActivityForResult(i, REQ_GAME_FOLDER);
    }

    private void chooseArchive(boolean multiple, int requestCode) {
        Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        i.addCategory(Intent.CATEGORY_OPENABLE);
        i.setType("*/*");
        i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, multiple);
        i.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{
                "application/zip", "application/x-zip-compressed",
                "application/vnd.rar", "application/x-rar-compressed",
                "application/octet-stream"
        });
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        startActivityForResult(i, requestCode);
    }

    private void chooseFolder(int requestCode) {
        Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PREFIX_URI_PERMISSION);
        startActivityForResult(i, requestCode);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (resultCode != RESULT_OK || data == null) return;

        if (requestCode == REQ_GAME_FOLDER) {
            Uri uri = data.getData();
            if (uri == null) return;
            int flags = data.getFlags() & (Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            try { getContentResolver().takePersistableUriPermission(uri, flags); } catch (SecurityException ignored) {}
            gameRootUri = uri;
            getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(KEY_GAME_URI, uri.toString()).apply();
            refreshUi();
            validateGameFolder();
            return;
        }

        if (requestCode == REQ_CHAR_SINGLE || requestCode == REQ_CHAR_MULTI) {
            List<Uri> uris = selectedUris(data);
            if (!uris.isEmpty()) installCharacterArchives(uris);
            return;
        }

        if (requestCode == REQ_STAGE_SINGLE || requestCode == REQ_STAGE_MULTI) {
            List<Uri> uris = selectedUris(data);
            if (!uris.isEmpty()) installStageArchives(uris);
            return;
        }

        Uri uri = data.getData();
        if (uri == null) return;
        if (requestCode == REQ_CHAR_FOLDER) installUnpackedCharacter(uri);
        else if (requestCode == REQ_STAGE_FOLDER) installUnpackedStage(uri);
    }

    private List<Uri> selectedUris(Intent data) {
        List<Uri> uris = new ArrayList<>();
        ClipData clip = data.getClipData();
        if (clip != null) {
            for (int n = 0; n < clip.getItemCount(); n++) uris.add(clip.getItemAt(n).getUri());
        } else if (data.getData() != null) {
            uris.add(data.getData());
        }
        return uris;
    }

    private void validateGameFolder() {
        busy("Finding active IKEMEN roster…");
        worker.execute(() -> {
            try {
                GameFiles g = resolveGameFiles();
                success("Folder valid ✓\n\nActive motif: " + g.motifPath + "\nActive roster: " + g.selectPath);
            } catch (Exception e) {
                fail(message(e));
            }
        });
    }

    private void installCharacterArchives(List<Uri> archiveUris) {
        busy("Preparing character install…");
        worker.execute(() -> {
            try {
                GameFiles g = resolveGameFiles();
                List<String> installed = new ArrayList<>();
                List<String> failed = new ArrayList<>();
                for (int i = 0; i < archiveUris.size(); i++) {
                    Uri uri = archiveUris.get(i);
                    String name = displayName(uri);
                    if (name == null) name = "character";
                    progress("Installing character " + (i + 1) + " / " + archiveUris.size() + "\n" + name);
                    try {
                        installed.add(installArchive(uri, name, g, false));
                    } catch (Exception e) {
                        failed.add(name + ": " + message(e));
                    }
                }
                finishBatch("character", installed, failed, g.selectPath);
            } catch (Exception e) {
                fail("Install failed.\n\n" + message(e));
            }
        });
    }

    private void installStageArchives(List<Uri> archiveUris) {
        busy("Preparing stage install…");
        worker.execute(() -> {
            try {
                GameFiles g = resolveGameFiles();
                List<String> installed = new ArrayList<>();
                List<String> failed = new ArrayList<>();
                for (int i = 0; i < archiveUris.size(); i++) {
                    Uri uri = archiveUris.get(i);
                    String name = displayName(uri);
                    if (name == null) name = "stage";
                    progress("Installing stage " + (i + 1) + " / " + archiveUris.size() + "\n" + name);
                    try {
                        installed.add(installArchive(uri, name, g, true));
                    } catch (Exception e) {
                        failed.add(name + ": " + message(e));
                    }
                }
                finishBatch("stage", installed, failed, g.selectPath);
            } catch (Exception e) {
                fail("Stage install failed.\n\n" + message(e));
            }
        });
    }

    private void finishBatch(String kind, List<String> installed, List<String> failed, String selectPath) {
        if (installed.isEmpty()) {
            StringBuilder out = new StringBuilder("No ").append(kind).append("s were installed.");
            for (String s : failed) out.append("\n\n• ").append(s);
            fail(out.toString());
            return;
        }
        StringBuilder out = new StringBuilder();
        out.append("Installed ").append(installed.size()).append(' ').append(kind).append("(s) ✓");
        out.append("\n\nActive roster: ").append(selectPath);
        for (String entry : installed) out.append("\n+ ").append(entry);
        if (!failed.isEmpty()) {
            out.append("\n\nFailed: ").append(failed.size());
            for (String s : failed) out.append("\n• ").append(s);
        }
        success(out.toString());
    }

    private String installArchive(Uri archiveUri, String name, GameFiles g, boolean stage) throws Exception {
        String lower = name.toLowerCase(Locale.ROOT);
        if (!lower.endsWith(".zip") && !lower.endsWith(".rar")) {
            throw new IOException("Choose a .zip or .rar archive.");
        }
        File temp = tempDir();
        try {
            try (InputStream raw = getContentResolver().openInputStream(archiveUri)) {
                if (raw == null) throw new IOException("Android could not open the archive.");
                if (lower.endsWith(".zip")) extractZip(raw, temp);
                else Junrar.extract(new BufferedInputStream(raw), temp);
            }
            return stage ? installStageFromLocal(temp, stripExtension(name), g)
                    : installCharacterFromLocal(temp, stripExtension(name), g);
        } finally {
            deleteTree(temp);
        }
    }

    private void installUnpackedCharacter(Uri treeUri) {
        busy("Reading character folder…");
        worker.execute(() -> {
            File temp = null;
            try {
                GameFiles g = resolveGameFiles();
                DocumentFile src = DocumentFile.fromTreeUri(this, treeUri);
                if (src == null || !src.isDirectory()) throw new IOException("Could not open that folder.");
                temp = tempDir();
                copySafFolderToLocal(src, temp);
                String entry = installCharacterFromLocal(temp, src.getName() == null ? "character" : src.getName(), g);
                success("Installed character ✓\n\nEntry: " + entry + "\nActive roster: " + g.selectPath);
            } catch (Exception e) {
                fail("Install failed.\n\n" + message(e));
            } finally {
                deleteTree(temp);
            }
        });
    }

    private void installUnpackedStage(Uri treeUri) {
        busy("Reading stage folder…");
        worker.execute(() -> {
            File temp = null;
            try {
                GameFiles g = resolveGameFiles();
                DocumentFile src = DocumentFile.fromTreeUri(this, treeUri);
                if (src == null || !src.isDirectory()) throw new IOException("Could not open that folder.");
                temp = tempDir();
                copySafFolderToLocal(src, temp);
                String entry = installStageFromLocal(temp, src.getName() == null ? "stage" : src.getName(), g);
                success("Installed stage ✓\n\nEntry: " + entry + "\nActive roster: " + g.selectPath);
            } catch (Exception e) {
                fail("Stage install failed.\n\n" + message(e));
            } finally {
                deleteTree(temp);
            }
        });
    }

    private String installCharacterFromLocal(File extractedRoot, String hint, GameFiles g) throws Exception {
        DefPick pick = findBestCharacterDef(extractedRoot, hint);
        if (pick == null) {
            List<File> defs = new ArrayList<>();
            collectDefs(extractedRoot, defs);
            if (defs.isEmpty()) throw new IOException("No .def file was found anywhere in this character package.");
            throw new IOException("I found .def files, but none looked like a playable character definition.");
        }

        File def = pick.file;
        File sourceDir = def.getParentFile();
        String desired = sourceDir.equals(extractedRoot) ? stripExtension(def.getName()) : sourceDir.getName();
        desired = sanitize(desired);
        String targetName = uniqueName(g.charsDir, desired);
        DocumentFile target = g.charsDir.createDirectory(targetName);
        if (target == null) throw new IOException("Could not create chars/" + targetName + ".");

        try {
            copyLocalDirExact(sourceDir, target);
            String entry = targetName + "/" + def.getName();
            addCharacterRosterEntries(g, Arrays.asList(entry));
            return entry;
        } catch (Exception e) {
            target.delete();
            throw e;
        }
    }

    private String installStageFromLocal(File extractedRoot, String hint, GameFiles g) throws Exception {
        DefPick pick = findBestStageDef(extractedRoot, hint);
        if (pick == null) {
            List<File> defs = new ArrayList<>();
            collectDefs(extractedRoot, defs);
            if (defs.isEmpty()) throw new IOException("No .def file was found anywhere in this stage package.");
            throw new IOException("I found .def files, but none looked like a stage definition.");
        }

        File def = pick.file;
        File sourceDir = def.getParentFile();
        String desired = sourceDir.equals(extractedRoot) ? stripExtension(def.getName()) : sourceDir.getName();
        desired = sanitize(desired);
        String targetName = uniqueName(g.stagesDir, desired);

        StageMusicResult music = prepareStageMusic(sourceDir, def, targetName, g);
        DocumentFile target = g.stagesDir.createDirectory(targetName);
        if (target == null) throw new IOException("Could not create stages/" + targetName + ".");

        try {
            copyLocalDirExact(sourceDir, target);
            String entry = "stages/" + targetName + "/" + def.getName();
            addStageRosterEntries(g, Arrays.asList(entry));
            if (music.assignedPath != null) return entry + "  [music: " + music.assignedPath + "]";
            return entry;
        } catch (Exception e) {
            target.delete();
            throw e;
        }
    }

    private StageMusicResult prepareStageMusic(File sourceDir, File stageDef, String targetName, GameFiles g) throws IOException {
        List<File> audio = new ArrayList<>();
        collectAudio(sourceDir, audio);
        String text = readLocalLatin1(stageDef, 1024 * 1024);
        String configured = iniValue(text, "Music", "bgMusic");
        if (configured == null) configured = iniValue(text, "Music", "bgm");
        configured = unquote(configured == null ? "" : configured.trim());

        File chosen = null;
        if (!configured.isBlank()) {
            chosen = findPackagedFile(sourceDir, configured, audio);
        } else if (audio.size() == 1) {
            chosen = audio.get(0);
        }

        if (chosen == null) return new StageMusicResult(null);

        String soundName = uniqueFileName(g.soundDir, sanitizeFileName(targetName + "__" + chosen.getName()));
        DocumentFile dest = createExactFile(g.soundDir, soundName);
        try (InputStream in = new BufferedInputStream(new FileInputStream(chosen));
             OutputStream out = getContentResolver().openOutputStream(dest.getUri(), "w")) {
            if (out == null) throw new IOException("Could not write bundled stage music.");
            copyStream(in, out);
        }
        String newPath = "sound/" + soundName;
        String rewritten = setIniValue(text, "Music", "bgMusic", newPath);
        Files.write(stageDef.toPath(), rewritten.getBytes(StandardCharsets.ISO_8859_1));
        return new StageMusicResult(newPath);
    }

    private File findPackagedFile(File sourceDir, String configured, List<File> audio) {
        String clean = cleanPath(configured);
        File direct = new File(sourceDir, clean);
        if (direct.isFile()) return direct;
        String base = new File(clean).getName();
        for (File f : audio) {
            if (f.getName().equalsIgnoreCase(base)) return f;
        }
        return null;
    }

    private void repairExistingCharacters() {
        busy("Repairing/scanning chars/…");
        worker.execute(() -> {
            try {
                GameFiles g = resolveGameFiles();
                int renamed = repairMangledTextNames(g.charsDir);
                String roster = readText(g.selectFile);
                List<String> missing = new ArrayList<>();
                int detected = 0;
                for (DocumentFile dir : g.charsDir.listFiles()) {
                    if (!dir.isDirectory() || dir.getName() == null) continue;
                    SafDefPick def = findBestCharacterDefSaf(dir);
                    if (def == null || def.file.getName() == null) continue;
                    detected++;
                    String entry = dir.getName() + "/" + def.relativePath;
                    if (!rosterContains(roster, entry, "Characters")) missing.add(entry);
                }
                if (!missing.isEmpty()) addCharacterRosterEntries(g, missing);
                success("Character repair complete ✓\n\nRenamed broken .txt suffixes: " + renamed
                        + "\nDetected characters: " + detected
                        + "\nRegistered now: " + missing.size()
                        + "\nActive roster: " + g.selectPath);
            } catch (Exception e) {
                fail("Character repair failed.\n\n" + message(e));
            }
        });
    }

    private void repairExistingStages() {
        busy("Scanning stages/…");
        worker.execute(() -> {
            try {
                GameFiles g = resolveGameFiles();
                int renamed = repairMangledTextNames(g.stagesDir);
                String roster = readText(g.selectFile);
                List<SafDefPick> defs = new ArrayList<>();
                collectStageDefsSaf(g.stagesDir, "", defs);
                List<String> missing = new ArrayList<>();
                for (SafDefPick p : defs) {
                    String entry = "stages/" + p.relativePath;
                    if (!rosterContains(roster, entry, "ExtraStages")) missing.add(entry);
                }
                if (!missing.isEmpty()) addStageRosterEntries(g, missing);
                success("Stage scan complete ✓\n\nRenamed broken .txt suffixes: " + renamed
                        + "\nDetected stages: " + defs.size()
                        + "\nRegistered now: " + missing.size()
                        + "\nActive roster: " + g.selectPath);
            } catch (Exception e) {
                fail("Stage registration failed.\n\n" + message(e));
            }
        });
    }

    private int repairMangledTextNames(DocumentFile dir) {
        int count = 0;
        for (DocumentFile f : dir.listFiles()) {
            if (f.isDirectory()) {
                count += repairMangledTextNames(f);
                continue;
            }
            String name = f.getName();
            if (name == null) continue;
            String lower = name.toLowerCase(Locale.ROOT);
            if (!lower.endsWith(".txt")) continue;
            String withoutTxt = name.substring(0, name.length() - 4);
            String ext = extension(withoutTxt);
            if (!TEXT_EXTENSIONS.contains(ext)) continue;
            if (childExact(dir, withoutTxt) != null) continue;
            if (f.renameTo(withoutTxt)) count++;
        }
        return count;
    }

    private GameFiles resolveGameFiles() throws IOException {
        if (gameRootUri == null) throw new IOException("Choose your IKEMEN game folder first.");
        DocumentFile root = DocumentFile.fromTreeUri(this, gameRootUri);
        if (root == null || !root.isDirectory()) throw new IOException("The saved IKEMEN folder is no longer accessible.");
        if (!root.canWrite()) throw new IOException("The selected IKEMEN folder is read-only.");

        DocumentFile chars = child(root, "chars");
        if (chars == null) chars = root.createDirectory("chars");
        DocumentFile stages = child(root, "stages");
        if (stages == null) stages = root.createDirectory("stages");
        DocumentFile sound = child(root, "sound");
        if (sound == null) sound = root.createDirectory("sound");
        if (chars == null || stages == null || sound == null) throw new IOException("Could not access/create chars, stages, or sound folders.");

        String motifPath = "data/ikemen1/system.def";
        DocumentFile save = child(root, "save");
        DocumentFile config = save == null ? null : child(save, "config.ini");
        if (config != null && config.isFile()) {
            String configured = iniValue(readText(config), "Config", "Motif");
            if (configured != null && !configured.isBlank()) motifPath = cleanPath(unquote(configured));
        }

        DocumentFile motif = path(root, motifPath);
        if (motif == null || !motif.isFile()) {
            String[] fallbacks = {"data/ikemen1/system.def", "data/system.def", "system.def"};
            motif = null;
            for (String p : fallbacks) {
                DocumentFile candidate = path(root, p);
                if (candidate != null && candidate.isFile()) {
                    motif = candidate;
                    motifPath = p;
                    break;
                }
            }
        }
        if (motif == null) throw new IOException("Could not locate the active motif system.def.");

        String selectName = iniValue(readText(motif), "Files", "select");
        if (selectName == null || selectName.isBlank()) selectName = "select.def";
        selectName = cleanPath(unquote(selectName));
        String motifDir = parentPath(motifPath);

        List<String> candidates = new ArrayList<>();
        candidates.add(join(motifDir, selectName));
        candidates.add(join("data", selectName));
        candidates.add(selectName);
        candidates.add("data/ikemen1/select.def");
        candidates.add("data/select.def");

        DocumentFile select = null;
        String selectPath = null;
        for (String candidatePath : candidates) {
            candidatePath = cleanPath(candidatePath);
            DocumentFile candidate = path(root, candidatePath);
            if (candidate != null && candidate.isFile()) {
                select = candidate;
                selectPath = candidatePath;
                break;
            }
        }
        if (select == null) {
            throw new IOException("The active motif was found but its select.def could not be resolved.\n\nMotif: "
                    + motifPath + "\nselect = " + selectName + "\nTried: " + String.join(", ", candidates));
        }

        DocumentFile selectDir = selectPath.contains("/") ? path(root, parentPath(selectPath)) : root;
        if (selectDir == null || !selectDir.isDirectory()) throw new IOException("Could not resolve the active roster directory.");
        return new GameFiles(root, chars, stages, sound, motifPath, selectPath, selectDir, select);
    }

    private void addCharacterRosterEntries(GameFiles g, List<String> requested) throws IOException {
        addRosterEntries(g, requested, "Characters", true);
    }

    private void addStageRosterEntries(GameFiles g, List<String> requested) throws IOException {
        addRosterEntries(g, requested, "ExtraStages", false);
    }

    private void addRosterEntries(GameFiles g, List<String> requested, String section, boolean beforeRandomSelect) throws IOException {
        String original = readText(g.selectFile);
        List<String> add = new ArrayList<>();
        for (String entry : requested) {
            if (!rosterContains(original, entry, section)) add.add(entry);
        }
        if (add.isEmpty()) return;

        String stamp = new SimpleDateFormat("yyyyMMdd-HHmmss-SSS", Locale.US).format(new Date());
        DocumentFile backup = createExactFile(g.selectDir, "select.def.backup-" + stamp);
        writeText(backup, original);
        String updated = insertIntoSection(original, section, add, beforeRandomSelect);
        writeText(g.selectFile, updated);
    }

    private static String insertIntoSection(String original, String section, List<String> entries, boolean beforeRandomSelect) {
        String eol = original.contains("\r\n") ? "\r\n" : "\n";
        List<String> lines = new ArrayList<>(Arrays.asList(original.split("\\r?\\n", -1)));
        int header = -1;
        int nextSection = lines.size();
        for (int i = 0; i < lines.size(); i++) {
            if (lines.get(i).trim().equalsIgnoreCase("[" + section + "]")) {
                header = i;
                for (int j = i + 1; j < lines.size(); j++) {
                    String t = lines.get(j).trim();
                    if (t.startsWith("[") && t.endsWith("]")) {
                        nextSection = j;
                        break;
                    }
                }
                break;
            }
        }
        if (header < 0) {
            if (!original.endsWith("\n") && !original.endsWith("\r")) lines.add("");
            lines.add("[" + section + "]");
            lines.addAll(entries);
            return String.join(eol, lines);
        }

        int insert = nextSection;
        if (beforeRandomSelect) {
            for (int i = header + 1; i < nextSection; i++) {
                String clean = stripComment(lines.get(i)).trim().toLowerCase(Locale.ROOT);
                if (clean.equals("randomselect") || clean.startsWith("randomselect,")) {
                    insert = i;
                    break;
                }
            }
        }
        lines.addAll(insert, entries);
        return String.join(eol, lines);
    }

    private static boolean rosterContains(String text, String entry, String section) {
        String wanted = entry.replace('\\', '/').trim();
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
            String first = clean.split(",", 2)[0].trim().replace('\\', '/');
            if (first.equalsIgnoreCase(wanted)) return true;
        }
        return false;
    }

    private DefPick findBestCharacterDef(File root, String hint) throws IOException {
        List<File> defs = new ArrayList<>();
        collectDefs(root, defs);
        String normalizedHint = normalize(hint);
        DefPick best = null;
        for (File def : defs) {
            String text = readLocalLatin1(def, 256 * 1024).toLowerCase(Locale.ROOT);
            boolean info = hasSection(text, "info");
            boolean files = hasSection(text, "files");
            boolean cmd = hasKey(text, "cmd");
            boolean sprite = hasKey(text, "sprite") || hasKey(text, "spr");
            boolean anim = hasKey(text, "anim");
            boolean stage = isStageText(text);
            int score = (info ? 100 : 0) + (files ? 25 : 0) + (cmd ? 30 : 0) + (sprite ? 30 : 0) + (anim ? 15 : 0);
            if (stage) score -= 300;
            String base = normalize(stripExtension(def.getName()));
            String parent = normalize(def.getParentFile().getName());
            if (base.equals(parent)) score += 25;
            if (!normalizedHint.isEmpty() && (base.equals(normalizedHint) || parent.equals(normalizedHint))) score += 35;
            boolean likely = !stage && (info || (files && (cmd || sprite || anim)));
            if (likely && (best == null || score > best.score)) best = new DefPick(def, score);
        }
        if (best != null) return best;
        if (defs.size() == 1 && !isStageText(readLocalLatin1(defs.get(0), 256 * 1024).toLowerCase(Locale.ROOT))) {
            return new DefPick(defs.get(0), 0);
        }
        return null;
    }

    private DefPick findBestStageDef(File root, String hint) throws IOException {
        List<File> defs = new ArrayList<>();
        collectDefs(root, defs);
        String normalizedHint = normalize(hint);
        DefPick best = null;
        for (File def : defs) {
            String text = readLocalLatin1(def, 512 * 1024).toLowerCase(Locale.ROOT);
            int score = 0;
            if (hasSection(text, "camera")) score += 60;
            if (hasSection(text, "stageinfo")) score += 80;
            if (hasSection(text, "bgdef")) score += 80;
            if (hasSection(text, "playerinfo")) score += 30;
            if (hasSection(text, "bound")) score += 20;
            if (hasSection(text, "info")) score += 10;
            if (hasSection(text, "files") && hasKey(text, "cmd")) score -= 200;
            String base = normalize(stripExtension(def.getName()));
            String parent = normalize(def.getParentFile().getName());
            if (base.equals(parent)) score += 15;
            if (!normalizedHint.isEmpty() && (base.equals(normalizedHint) || parent.equals(normalizedHint))) score += 20;
            if (isStageText(text) && (best == null || score > best.score)) best = new DefPick(def, score);
        }
        return best;
    }

    private static boolean isStageText(String lower) {
        return hasSection(lower, "stageinfo") || (hasSection(lower, "camera") && hasSection(lower, "bgdef"));
    }

    private SafDefPick findBestCharacterDefSaf(DocumentFile dir) {
        List<SafDefPick> defs = new ArrayList<>();
        collectDefsSaf(dir, "", defs);
        if (defs.isEmpty()) return null;
        SafDefPick best = null;
        int bestScore = Integer.MIN_VALUE;
        String folder = normalize(dir.getName());
        for (SafDefPick p : defs) {
            try {
                String text = readText(p.file).toLowerCase(Locale.ROOT);
                if (isStageText(text)) continue;
                int score = hasSection(text, "info") ? 50 : 0;
                if (normalize(stripExtension(p.file.getName())).equals(folder)) score += 40;
                if (hasSection(text, "files")) score += 20;
                if (score > bestScore) {
                    best = p;
                    bestScore = score;
                }
            } catch (Exception ignored) {}
        }
        return best != null ? best : defs.get(0);
    }

    private void collectStageDefsSaf(DocumentFile dir, String prefix, List<SafDefPick> out) {
        for (DocumentFile f : dir.listFiles()) {
            String name = f.getName();
            if (name == null) continue;
            String rel = prefix.isEmpty() ? name : prefix + "/" + name;
            if (f.isDirectory()) {
                collectStageDefsSaf(f, rel, out);
            } else if (f.isFile() && name.toLowerCase(Locale.ROOT).endsWith(".def")) {
                try {
                    String text = readText(f).toLowerCase(Locale.ROOT);
                    if (isStageText(text)) out.add(new SafDefPick(f, rel));
                } catch (Exception ignored) {}
            }
        }
    }

    private void collectDefsSaf(DocumentFile dir, String prefix, List<SafDefPick> out) {
        for (DocumentFile f : dir.listFiles()) {
            String name = f.getName();
            if (name == null) continue;
            String rel = prefix.isEmpty() ? name : prefix + "/" + name;
            if (f.isDirectory()) collectDefsSaf(f, rel, out);
            else if (f.isFile() && name.toLowerCase(Locale.ROOT).endsWith(".def")) out.add(new SafDefPick(f, rel));
        }
    }

    private static boolean hasSection(String text, String section) {
        for (String raw : text.split("\\r?\\n")) {
            String line = stripComment(raw).trim();
            if (line.startsWith("[") && line.endsWith("]")) {
                String name = line.substring(1, line.length() - 1).trim();
                if (name.equalsIgnoreCase(section)) return true;
            }
        }
        return false;
    }

    private static boolean hasKey(String text, String key) {
        for (String raw : text.split("\\r?\\n")) {
            String line = stripComment(raw).trim();
            int eq = line.indexOf('=');
            if (eq < 0) continue;
            if (line.substring(0, eq).trim().equalsIgnoreCase(key)) return true;
        }
        return false;
    }

    private void collectDefs(File f, List<File> out) {
        if (f == null || !f.exists()) return;
        if (f.isFile()) {
            if (f.getName().toLowerCase(Locale.ROOT).endsWith(".def")) out.add(f);
            return;
        }
        File[] children = f.listFiles();
        if (children != null) for (File c : children) collectDefs(c, out);
    }

    private void collectAudio(File f, List<File> out) {
        if (f == null || !f.exists()) return;
        if (f.isFile()) {
            if (AUDIO_EXTENSIONS.contains(extension(f.getName()))) out.add(f);
            return;
        }
        File[] children = f.listFiles();
        if (children != null) for (File c : children) collectAudio(c, out);
    }

    private DocumentFile child(DocumentFile parent, String name) {
        if (parent == null || !parent.isDirectory()) return null;
        for (DocumentFile f : parent.listFiles()) {
            if (f.getName() != null && f.getName().equalsIgnoreCase(name)) return f;
        }
        return null;
    }

    private DocumentFile childExact(DocumentFile parent, String name) {
        if (parent == null || !parent.isDirectory()) return null;
        for (DocumentFile f : parent.listFiles()) {
            if (name.equals(f.getName())) return f;
        }
        return null;
    }

    private DocumentFile path(DocumentFile root, String value) {
        String clean = cleanPath(value);
        if (clean.isEmpty()) return root;
        DocumentFile current = root;
        for (String part : clean.split("/")) {
            if (part.isEmpty() || part.equals(".")) continue;
            if (part.equals("..")) return null;
            current = child(current, part);
            if (current == null) return null;
        }
        return current;
    }

    private String uniqueName(DocumentFile parent, String wanted) {
        String name = wanted;
        int n = 2;
        while (child(parent, name) != null) name = wanted + "_" + n++;
        return name;
    }

    private String uniqueFileName(DocumentFile parent, String wanted) {
        if (child(parent, wanted) == null) return wanted;
        String base = stripExtension(wanted);
        String ext = wanted.substring(base.length());
        int n = 2;
        String candidate;
        do candidate = base + "_" + n++ + ext; while (child(parent, candidate) != null);
        return candidate;
    }

    private DocumentFile createExactFile(DocumentFile parent, String name) throws IOException {
        DocumentFile file = parent.createFile("application/octet-stream", name);
        if (file == null) throw new IOException("Could not create file " + name);
        String actual = file.getName();
        if (!name.equals(actual)) {
            if (!file.renameTo(name)) {
                file.delete();
                throw new IOException("Android changed filename '" + name + "' to '" + actual + "' and exact rename failed.");
            }
            DocumentFile renamed = childExact(parent, name);
            if (renamed != null) file = renamed;
        }
        return file;
    }

    private static String stripComment(String line) {
        int semi = line.indexOf(';');
        return semi >= 0 ? line.substring(0, semi) : line;
    }

    private static String iniValue(String text, String section, String key) {
        boolean inSection = false;
        for (String raw : text.split("\\r?\\n")) {
            String line = stripComment(raw).trim();
            if (line.isEmpty()) continue;
            if (line.startsWith("[") && line.endsWith("]")) {
                inSection = line.substring(1, line.length() - 1).trim().equalsIgnoreCase(section);
                continue;
            }
            if (!inSection) continue;
            int eq = line.indexOf('=');
            if (eq < 0) continue;
            if (line.substring(0, eq).trim().equalsIgnoreCase(key)) return line.substring(eq + 1).trim();
        }
        return null;
    }

    private static String setIniValue(String text, String section, String key, String value) {
        String eol = text.contains("\r\n") ? "\r\n" : "\n";
        List<String> lines = new ArrayList<>(Arrays.asList(text.split("\\r?\\n", -1)));
        int header = -1;
        int end = lines.size();
        for (int i = 0; i < lines.size(); i++) {
            if (lines.get(i).trim().equalsIgnoreCase("[" + section + "]")) {
                header = i;
                for (int j = i + 1; j < lines.size(); j++) {
                    String t = lines.get(j).trim();
                    if (t.startsWith("[") && t.endsWith("]")) { end = j; break; }
                }
                break;
            }
        }
        if (header < 0) {
            if (!lines.isEmpty() && !lines.get(lines.size() - 1).isEmpty()) lines.add("");
            lines.add("[" + section + "]");
            lines.add(key + " = " + value);
            return String.join(eol, lines);
        }
        for (int i = header + 1; i < end; i++) {
            String clean = stripComment(lines.get(i)).trim();
            int eq = clean.indexOf('=');
            if (eq >= 0 && clean.substring(0, eq).trim().equalsIgnoreCase(key)) {
                lines.set(i, key + " = " + value);
                return String.join(eol, lines);
            }
        }
        lines.add(header + 1, key + " = " + value);
        return String.join(eol, lines);
    }

    private String readText(DocumentFile file) throws IOException {
        try (InputStream in = getContentResolver().openInputStream(file.getUri())) {
            if (in == null) throw new IOException("Could not read " + file.getName());
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            copyStream(in, out);
            return out.toString(StandardCharsets.UTF_8);
        }
    }

    private void writeText(DocumentFile file, String text) throws IOException {
        try (OutputStream out = getContentResolver().openOutputStream(file.getUri(), "wt")) {
            if (out == null) throw new IOException("Could not write " + file.getName());
            out.write(text.getBytes(StandardCharsets.UTF_8));
        }
    }

    private String readLocalLatin1(File file, int maxBytes) throws IOException {
        try (InputStream in = new FileInputStream(file)) {
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

    private void extractZip(InputStream source, File destination) throws IOException {
        String rootCanonical = destination.getCanonicalPath();
        String base = rootCanonical + File.separator;
        try (ZipInputStream zip = new ZipInputStream(new BufferedInputStream(source))) {
            ZipEntry entry;
            byte[] buffer = new byte[64 * 1024];
            while ((entry = zip.getNextEntry()) != null) {
                String clean = entry.getName().replace('\\', '/');
                if (clean.startsWith("/") || clean.contains("../")) throw new IOException("Unsafe archive path: " + entry.getName());
                File outFile = new File(destination, clean);
                String canonical = outFile.getCanonicalPath();
                if (!canonical.equals(rootCanonical) && !canonical.startsWith(base)) throw new IOException("Unsafe archive path: " + entry.getName());
                if (entry.isDirectory()) {
                    if (!outFile.exists() && !outFile.mkdirs()) throw new IOException("Could not create " + outFile);
                } else {
                    File parent = outFile.getParentFile();
                    if (parent != null && !parent.exists() && !parent.mkdirs()) throw new IOException("Could not create " + parent);
                    try (OutputStream out = new BufferedOutputStream(new FileOutputStream(outFile))) {
                        int n;
                        while ((n = zip.read(buffer)) >= 0) if (n > 0) out.write(buffer, 0, n);
                    }
                }
                zip.closeEntry();
            }
        }
    }

    private void copyLocalDirExact(File sourceDir, DocumentFile targetDir) throws IOException {
        File[] children = sourceDir.listFiles();
        if (children == null) throw new IOException("Could not read extracted package folder.");
        for (File child : children) copyLocalToSafExact(child, targetDir);
    }

    private void copyLocalToSafExact(File source, DocumentFile parent) throws IOException {
        if (source.isDirectory()) {
            DocumentFile dir = parent.createDirectory(source.getName());
            if (dir == null) throw new IOException("Could not create folder " + source.getName());
            File[] children = source.listFiles();
            if (children != null) for (File child : children) copyLocalToSafExact(child, dir);
        } else {
            DocumentFile file = createExactFile(parent, source.getName());
            try (InputStream in = new BufferedInputStream(new FileInputStream(source));
                 OutputStream out = getContentResolver().openOutputStream(file.getUri(), "w")) {
                if (out == null) throw new IOException("Could not write " + source.getName());
                copyStream(in, out);
            }
        }
    }

    private void copySafFolderToLocal(DocumentFile source, File target) throws IOException {
        for (DocumentFile child : source.listFiles()) {
            String name = child.getName();
            if (name == null || name.isBlank()) continue;
            File dest = new File(target, name);
            if (child.isDirectory()) {
                if (!dest.exists() && !dest.mkdirs()) throw new IOException("Could not create temporary folder.");
                copySafFolderToLocal(child, dest);
            } else if (child.isFile()) {
                File parent = dest.getParentFile();
                if (parent != null && !parent.exists()) parent.mkdirs();
                try (InputStream in = getContentResolver().openInputStream(child.getUri());
                     OutputStream out = new FileOutputStream(dest)) {
                    if (in == null) throw new IOException("Could not read " + name);
                    copyStream(in, out);
                }
            }
        }
    }

    private static String cleanPath(String value) {
        if (value == null) return "";
        String p = value.trim().replace('\\', '/');
        while (p.startsWith("./")) p = p.substring(2);
        while (p.startsWith("/")) p = p.substring(1);
        while (p.contains("//")) p = p.replace("//", "/");
        return p;
    }

    private static String parentPath(String value) {
        String p = cleanPath(value);
        int slash = p.lastIndexOf('/');
        return slash < 0 ? "" : p.substring(0, slash);
    }

    private static String join(String a, String b) {
        a = cleanPath(a);
        b = cleanPath(b);
        if (a.isEmpty()) return b;
        if (b.isEmpty()) return a;
        return a + "/" + b;
    }

    private static String normalize(String value) {
        if (value == null) return "";
        return stripExtension(value).toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]", "");
    }

    private static String stripExtension(String name) {
        int dot = name == null ? -1 : name.lastIndexOf('.');
        return dot > 0 ? name.substring(0, dot) : name;
    }

    private static String extension(String name) {
        int dot = name == null ? -1 : name.lastIndexOf('.');
        return dot >= 0 ? name.substring(dot).toLowerCase(Locale.ROOT) : "";
    }

    private static String sanitize(String name) {
        String clean = name.replaceAll("[\\\\/:*?\"<>|]", "_").trim().replaceAll("\\s+", " ");
        return clean.isEmpty() ? "content" : clean;
    }

    private static String sanitizeFileName(String name) {
        return name.replaceAll("[\\\\/:*?\"<>|]", "_").trim();
    }

    private static String unquote(String value) {
        if (value == null) return "";
        String v = value.trim();
        if (v.length() >= 2 && ((v.startsWith("\"") && v.endsWith("\"")) || (v.startsWith("'") && v.endsWith("'")))) {
            return v.substring(1, v.length() - 1).trim();
        }
        return v;
    }

    private void copyStream(InputStream in, OutputStream out) throws IOException {
        byte[] buf = new byte[64 * 1024];
        int n;
        while ((n = in.read(buf)) >= 0) if (n > 0) out.write(buf, 0, n);
    }

    private File tempDir() throws IOException {
        File dir = new File(getCacheDir(), "install-" + System.nanoTime());
        if (!dir.mkdirs()) throw new IOException("Could not create temporary extraction folder.");
        return dir;
    }

    private void deleteTree(File file) {
        if (file == null || !file.exists()) return;
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) for (File child : children) deleteTree(child);
        }
        //noinspection ResultOfMethodCallIgnored
        file.delete();
    }

    private String displayName(Uri uri) {
        Cursor cursor = null;
        try {
            cursor = getContentResolver().query(uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null);
            if (cursor != null && cursor.moveToFirst()) {
                int index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (index >= 0) return cursor.getString(index);
            }
        } finally {
            if (cursor != null) cursor.close();
        }
        return uri.getLastPathSegment();
    }

    private String message(Throwable e) {
        String m = e.getMessage();
        if (m == null || m.isBlank()) m = e.getClass().getSimpleName();
        String lower = m.toLowerCase(Locale.ROOT);
        if (lower.contains("password") || lower.contains("encrypted")) {
            return "This archive appears to be password-protected. Extract it first, then use the unpacked-folder option.\n\n" + m;
        }
        return m;
    }

    private static class DefPick {
        final File file;
        final int score;
        DefPick(File file, int score) { this.file = file; this.score = score; }
    }

    private static class SafDefPick {
        final DocumentFile file;
        final String relativePath;
        SafDefPick(DocumentFile file, String relativePath) { this.file = file; this.relativePath = relativePath; }
    }

    private static class StageMusicResult {
        final String assignedPath;
        StageMusicResult(String assignedPath) { this.assignedPath = assignedPath; }
    }

    private static class GameFiles {
        final DocumentFile root;
        final DocumentFile charsDir;
        final DocumentFile stagesDir;
        final DocumentFile soundDir;
        final String motifPath;
        final String selectPath;
        final DocumentFile selectDir;
        final DocumentFile selectFile;

        GameFiles(DocumentFile root, DocumentFile charsDir, DocumentFile stagesDir, DocumentFile soundDir,
                  String motifPath, String selectPath, DocumentFile selectDir, DocumentFile selectFile) {
            this.root = root;
            this.charsDir = charsDir;
            this.stagesDir = stagesDir;
            this.soundDir = soundDir;
            this.motifPath = motifPath;
            this.selectPath = selectPath;
            this.selectDir = selectDir;
            this.selectFile = selectFile;
        }
    }
}
