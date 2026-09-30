// Process-local compatibility for Landlock ABI 1 cross-directory publication.
// Keep the target atomic/no-clobber semantics; do not disable the filesystem fence.
import fs from 'node:fs';
import { dirname, basename, join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { syncBuiltinESMExports } from 'node:module';

const io = fs.promises;
const link = io.link.bind(io);
const rename = io.rename.bind(io);

async function publishSibling(source, target, operation) {
  const sibling = join(dirname(target), `.${basename(target)}.${randomUUID()}.publish`);
  let created = false;
  try {
    // Source read and destination write must still pass the original kernel fence.
    await io.copyFile(source, sibling, fs.constants.COPYFILE_EXCL);
    created = true;
    const handle = await io.open(sibling, 'r');
    try { await handle.sync(); } finally { await handle.close(); }
    await operation(sibling, target);
  } finally {
    if (created) await io.unlink(sibling).catch(error => {
      if (error.code !== 'ENOENT') throw error;
    });
  }
}

io.link = async function (source, target) {
  try { return await link(source, target); }
  catch (error) {
    if (error.code !== 'EXDEV') throw error;
    // link remains create-if-absent; a concurrent/existing target is never replaced.
    return publishSibling(source, target, link);
  }
};
io.rename = async function (source, target) {
  try { return await rename(source, target); }
  catch (error) {
    if (error.code !== 'EXDEV') throw error;
    await publishSibling(source, target, rename);
    await io.unlink(source);
  }
};
syncBuiltinESMExports();
