/**
 * C Drive窓口（Claude Code ⇔ Google Drive 受け渡し用）
 *
 * 目的：クラウドで動く Claude Code（C）が、大きな動画ファイルを
 *       Google Drive の「17LIVE録画」フォルダ以下に置いたり、そこから取得したりする。
 *
 * 安全のための制限
 *  - 読み書きできるのは ALLOWED_ROOTS（17LIVE録画）以下だけ
 *  - できるのは「新規作成」「一覧」「情報取得」「ダウンロード」だけ
 *    （上書き・削除・共有設定の変更・移動はできない）
 *  - 同じフォルダに同名ファイルがあるときは作成を拒否する
 *  - すべての操作に合言葉（setup() が作るランダムな文字列）が必要
 *
 * 合言葉は setup() を実行すると作られ、マイドライブ直下に
 * 「C窓口キー_共有禁止.txt」として保存される（このファイルは誰にも共有しないこと）。
 * 合言葉を変えたいときは、もう一度 setup() を実行する（古い合言葉は無効になる）。
 */

const ALLOWED_ROOTS = ['1QHsRpxESWytRwjlK49Ltzq7uYMjc63ZH']; // 17LIVE録画
const KEY_FILE_NAME = 'C窓口キー_共有禁止.txt';
const MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024;  // 2 GB
const MAX_CHUNK_BYTES = 8 * 1024 * 1024;        // 1回の送受信は 8 MB まで
const CHUNK_UNIT = 256 * 1024;                  // Drive の分割アップロードの単位
const ALLOWED_MIME = ['video/mp4', 'audio/mp4', 'audio/x-m4a', 'text/plain', 'text/markdown',
                      'application/json', 'image/jpeg', 'image/png', 'application/octet-stream'];
const API = 'https://www.googleapis.com';

/* ---------- 初回設定（エディタから1回だけ実行） ---------- */
function setup() {
  const key = Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, '');
  PropertiesService.getScriptProperties().setProperty('KEY', key);
  const old = DriveApp.getRootFolder().getFilesByName(KEY_FILE_NAME);
  while (old.hasNext()) old.next().setTrashed(true);
  DriveApp.getRootFolder().createFile(KEY_FILE_NAME, key, 'text/plain');
  // 権限確認のため一度だけ外部通信も実行しておく
  UrlFetchApp.fetch(API + '/drive/v3/about?fields=user', authOpt_({}));
  console.log('設定完了：マイドライブ直下に「' + KEY_FILE_NAME + '」を作成しました。');
}

/* ---------- 入口 ---------- */
function doGet() {
  return json_({ ok: true, service: 'C Drive窓口', version: 1 });
}

function doPost(e) {
  try {
    const req = JSON.parse(e.postData.contents);
    const key = PropertiesService.getScriptProperties().getProperty('KEY');
    if (!key || req.key !== key) return json_({ ok: false, error: 'unauthorized' });
    switch (req.action) {
      case 'list': return json_(list_(req));
      case 'info': return json_(info_(req));
      case 'upload_init': return json_(uploadInit_(req));
      case 'upload_chunk': return json_(uploadChunk_(req));
      case 'download_chunk': return json_(downloadChunk_(req));
      default: return json_({ ok: false, error: 'unknown action' });
    }
  } catch (err) {
    return json_({ ok: false, error: String(err && err.message || err) });
  }
}

/* ---------- 操作 ---------- */
function list_(req) {
  const folder = DriveApp.getFolderById(req.folderId);
  mustBeUnderRoot_(req.folderId, true);
  const out = [];
  const fs = folder.getFiles();
  while (fs.hasNext() && out.length < 500) {
    const f = fs.next();
    out.push({ id: f.getId(), name: f.getName(), size: f.getSize(), mimeType: f.getMimeType() });
  }
  const ds = folder.getFolders();
  while (ds.hasNext() && out.length < 600) {
    const d = ds.next();
    out.push({ id: d.getId(), name: d.getName(), mimeType: 'application/vnd.google-apps.folder' });
  }
  return { ok: true, folder: folder.getName(), items: out };
}

function info_(req) {
  mustBeUnderRoot_(req.fileId, false);
  const r = UrlFetchApp.fetch(API + '/drive/v3/files/' + encodeURIComponent(req.fileId) +
      '?fields=id,name,size,md5Checksum,mimeType,parents,createdTime&supportsAllDrives=true', authOpt_({}));
  if (r.getResponseCode() !== 200) return { ok: false, error: 'drive ' + r.getResponseCode() + ' ' + r.getContentText() };
  return { ok: true, file: JSON.parse(r.getContentText()) };
}

function uploadInit_(req) {
  const name = String(req.name || '');
  const size = Number(req.size);
  const mime = String(req.mimeType || 'application/octet-stream');
  if (!name || name.length > 200 || /[\/\\\u0000-\u001f]/.test(name)) return { ok: false, error: 'bad name' };
  if (!(size > 0 && size <= MAX_FILE_BYTES)) return { ok: false, error: 'bad size' };
  if (ALLOWED_MIME.indexOf(mime) < 0) return { ok: false, error: 'mimeType not allowed' };
  const folder = DriveApp.getFolderById(req.folderId);
  mustBeUnderRoot_(req.folderId, true);
  if (folder.getFilesByName(name).hasNext()) return { ok: false, error: 'exists' };

  const r = UrlFetchApp.fetch(API + '/upload/drive/v3/files?uploadType=resumable&supportsAllDrives=true', authOpt_({
    method: 'post',
    contentType: 'application/json; charset=UTF-8',
    payload: JSON.stringify({ name: name, parents: [req.folderId], mimeType: mime }),
    headers: { 'X-Upload-Content-Type': mime, 'X-Upload-Content-Length': String(size) },
  }));
  const loc = header_(r, 'location');
  if (r.getResponseCode() !== 200 || !loc) return { ok: false, error: 'init ' + r.getResponseCode() + ' ' + r.getContentText() };
  const uploadId = Utilities.getUuid();
  CacheService.getScriptCache().put('up_' + uploadId, JSON.stringify({ uri: loc, size: size }), 21600);
  return { ok: true, uploadId: uploadId, chunkUnit: CHUNK_UNIT, maxChunk: MAX_CHUNK_BYTES };
}

function uploadChunk_(req) {
  const s = CacheService.getScriptCache().get('up_' + req.uploadId);
  if (!s) return { ok: false, error: 'unknown or expired uploadId' };
  const st = JSON.parse(s);
  const bytes = Utilities.base64Decode(req.data);
  const start = Number(req.offset);
  const end = start + bytes.length - 1;
  if (bytes.length === 0 || bytes.length > MAX_CHUNK_BYTES || end >= st.size) return { ok: false, error: 'bad chunk' };
  if (end + 1 < st.size && bytes.length % CHUNK_UNIT !== 0) return { ok: false, error: 'chunk must be a multiple of 256KiB' };
  const r = UrlFetchApp.fetch(st.uri, authOpt_({
    method: 'put',
    contentType: 'application/octet-stream',
    payload: bytes,
    headers: { 'Content-Range': 'bytes ' + start + '-' + end + '/' + st.size },
    followRedirects: false,
  }));
  const code = r.getResponseCode();
  if (code === 308) return { ok: true, done: false, range: header_(r, 'range') || '' };
  if (code === 200 || code === 201) {
    CacheService.getScriptCache().remove('up_' + req.uploadId);
    return { ok: true, done: true, file: JSON.parse(r.getContentText()) };
  }
  return { ok: false, error: 'chunk ' + code + ' ' + r.getContentText() };
}

function downloadChunk_(req) {
  mustBeUnderRoot_(req.fileId, false);
  const start = Number(req.offset);
  const len = Math.min(Number(req.length || MAX_CHUNK_BYTES), MAX_CHUNK_BYTES);
  const r = UrlFetchApp.fetch(API + '/drive/v3/files/' + encodeURIComponent(req.fileId) +
      '?alt=media&supportsAllDrives=true', authOpt_({ headers: { Range: 'bytes=' + start + '-' + (start + len - 1) } }));
  const code = r.getResponseCode();
  if (code !== 206 && code !== 200) return { ok: false, error: 'download ' + code };
  const b = r.getContent();
  return { ok: true, offset: start, length: b.length, data: Utilities.base64Encode(b) };
}

/* ---------- 補助 ---------- */
function mustBeUnderRoot_(id, isFolder) {
  const cache = CacheService.getScriptCache();
  if (cache.get('ok_' + id)) return;
  let parents = isFolder ? DriveApp.getFolderById(id).getParents() : DriveApp.getFileById(id).getParents();
  if (isFolder && ALLOWED_ROOTS.indexOf(id) >= 0) { cache.put('ok_' + id, '1', 3600); return; }
  for (let depth = 0; depth < 20 && parents.hasNext(); depth++) {
    const p = parents.next();
    if (ALLOWED_ROOTS.indexOf(p.getId()) >= 0) { cache.put('ok_' + id, '1', 3600); return; }
    parents = p.getParents();
  }
  throw new Error('outside allowed folders');
}

function authOpt_(o) {
  o.headers = Object.assign({ Authorization: 'Bearer ' + ScriptApp.getOAuthToken() }, o.headers || {});
  o.muteHttpExceptions = true;
  return o;
}

function header_(resp, name) {
  const h = resp.getAllHeaders();
  for (const k in h) if (k.toLowerCase() === name) return Array.isArray(h[k]) ? h[k][0] : h[k];
  return null;
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
