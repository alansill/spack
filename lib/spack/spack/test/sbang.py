# Copyright 2013-2021 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

"""\
Test that Spack's shebang filtering works correctly.
"""
import filecmp
import os
import shutil
import stat
import tempfile

import pytest

import llnl.util.filesystem as fs

import spack.hooks.sbang as sbang
import spack.paths
import spack.store
from spack.util.executable import which

too_long = sbang.shebang_limit + 1


short_line        = "#!/this/is/short/bin/bash\n"
long_line         = "#!/this/" + ('x' * too_long) + "/is/long\n"

lua_line          = "#!/this/" + ('x' * too_long) + "/is/lua\n"
lua_in_text       = ("line\n") * 100 + "lua\n" + ("line\n" * 100)
lua_line_patched  = "--!/this/" + ('x' * too_long) + "/is/lua\n"

node_line         = "#!/this/" + ('x' * too_long) + "/is/node\n"
node_in_text      = ("line\n") * 100 + "lua\n" + ("line\n" * 100)
node_line_patched = "//!/this/" + ('x' * too_long) + "/is/node\n"

php_line         = "#!/this/" + ('x' * too_long) + "/is/php\n"
php_in_text      = ("line\n") * 100 + "php\n" + ("line\n" * 100)
php_line_patched = "<?php #!/this/" + ('x' * too_long) + "/is/php\n"
php_line_patched2 = "?>\n"

sbang_line = '#!/bin/sh %s/bin/sbang\n' % spack.store.store.unpadded_root
last_line  = "last!\n"


@pytest.fixture  # type: ignore[no-redef]
def sbang_line():
    yield '#!/bin/sh %s/bin/sbang\n' % spack.store.layout.root


class ScriptDirectory(object):
    """Directory full of test scripts to run sbang instrumentation on."""
    def __init__(self, sbang_line):
        self.tempdir = tempfile.mkdtemp()

        self.directory = os.path.join(self.tempdir, 'dir')
        fs.mkdirp(self.directory)

        # Script with short shebang
        self.short_shebang = os.path.join(self.tempdir, 'short')
        with open(self.short_shebang, 'w') as f:
            f.write(short_line)
            f.write(last_line)

        # Script with long shebang
        self.long_shebang = os.path.join(self.tempdir, 'long')
        with open(self.long_shebang, 'w') as f:
            f.write(long_line)
            f.write(last_line)

        # Lua script with long shebang
        self.lua_shebang = os.path.join(self.tempdir, 'lua')
        with open(self.lua_shebang, 'w') as f:
            f.write(lua_line)
            f.write(last_line)

        # Lua script with long shebang
        self.lua_textbang = os.path.join(self.tempdir, 'lua_in_text')
        with open(self.lua_textbang, 'w') as f:
            f.write(short_line)
            f.write(lua_in_text)
            f.write(last_line)

        # Node script with long shebang
        self.node_shebang = os.path.join(self.tempdir, 'node')
        with open(self.node_shebang, 'w') as f:
            f.write(node_line)
            f.write(last_line)

        # Node script with long shebang
        self.node_textbang = os.path.join(self.tempdir, 'node_in_text')
        with open(self.node_textbang, 'w') as f:
            f.write(short_line)
            f.write(node_in_text)
            f.write(last_line)

        # php script with long shebang
        self.php_shebang = os.path.join(self.tempdir, 'php')
        with open(self.php_shebang, 'w') as f:
            f.write(php_line)
            f.write(last_line)

        # php script with long shebang
        self.php_textbang = os.path.join(self.tempdir, 'php_in_text')
        with open(self.php_textbang, 'w') as f:
            f.write(short_line)
            f.write(php_in_text)
            f.write(last_line)

        # Script already using sbang.
        self.has_sbang = os.path.join(self.tempdir, 'shebang')
        with open(self.has_sbang, 'w') as f:
            f.write(sbang_line)
            f.write(long_line)
            f.write(last_line)

        # Fake binary file.
        self.binary = os.path.join(self.tempdir, 'binary')
        tar = which('tar', required=True)
        tar('czf', self.binary, self.has_sbang)

    def destroy(self):
        shutil.rmtree(self.tempdir, ignore_errors=True)


@pytest.fixture
def script_dir(sbang_line):
    sdir = ScriptDirectory(sbang_line)
    yield sdir
    sdir.destroy()


def test_shebang_handling(script_dir, sbang_line):
    assert sbang.shebang_too_long(script_dir.lua_shebang)
    assert sbang.shebang_too_long(script_dir.long_shebang)

    assert not sbang.shebang_too_long(script_dir.short_shebang)
    assert not sbang.shebang_too_long(script_dir.has_sbang)
    assert not sbang.shebang_too_long(script_dir.binary)
    assert not sbang.shebang_too_long(script_dir.directory)

    sbang.filter_shebangs_in_directory(script_dir.tempdir)

    # Make sure this is untouched
    with open(script_dir.short_shebang, 'r') as f:
        assert f.readline() == short_line
        assert f.readline() == last_line

    # Make sure this got patched.
    with open(script_dir.long_shebang, 'r') as f:
        assert f.readline() == sbang_line
        assert f.readline() == long_line
        assert f.readline() == last_line

    # Make sure this got patched.
    with open(script_dir.lua_shebang, 'r') as f:
        assert f.readline() == sbang_line
        assert f.readline() == lua_line_patched
        assert f.readline() == last_line

    # Make sure this got patched.
    with open(script_dir.node_shebang, 'r') as f:
        assert f.readline() == sbang_line
        assert f.readline() == node_line_patched
        assert f.readline() == last_line

    assert filecmp.cmp(script_dir.lua_textbang,
                       os.path.join(script_dir.tempdir, 'lua_in_text'))
    assert filecmp.cmp(script_dir.node_textbang,
                       os.path.join(script_dir.tempdir, 'node_in_text'))

    # Make sure this is untouched
    with open(script_dir.has_sbang, 'r') as f:
        assert f.readline() == sbang_line
        assert f.readline() == long_line
        assert f.readline() == last_line


def test_shebang_handles_non_writable_files(script_dir, sbang_line):
    # make a file non-writable
    st = os.stat(script_dir.long_shebang)
    not_writable_mode = st.st_mode & ~stat.S_IWRITE
    os.chmod(script_dir.long_shebang, not_writable_mode)

    test_shebang_handling(script_dir, sbang_line)

    st = os.stat(script_dir.long_shebang)
    assert oct(not_writable_mode) == oct(st.st_mode)


def check_sbang_installation():
    sbang_path = sbang.sbang_install_path()
    sbang_bin_dir = os.path.dirname(sbang_path)
    assert sbang_path.startswith(spack.store.store.unpadded_root)

    assert os.path.exists(sbang_path)
    assert fs.is_exe(sbang_path)

    status = os.stat(sbang_path)
    assert (status.st_mode & 0o777) == 0o755

    status = os.stat(sbang_bin_dir)
    assert (status.st_mode & 0o777) == 0o755


def test_install_sbang(install_mockery):
    sbang_path = sbang.sbang_install_path()
    sbang_bin_dir = os.path.dirname(sbang_path)

    assert sbang_path.startswith(spack.store.store.unpadded_root)
    assert not os.path.exists(sbang_bin_dir)

    sbang.install_sbang()
    check_sbang_installation()

    # put an invalid file in for sbang
    fs.mkdirp(sbang_bin_dir)
    with open(sbang_path, "w") as f:
        f.write("foo")

    sbang.install_sbang()
    check_sbang_installation()

    # install again and make sure sbang is still fine
    sbang.install_sbang()
    check_sbang_installation()


def test_install_sbang_too_long(tmpdir):
    root = str(tmpdir)
    num_extend = sbang.shebang_limit - len(root) - len('/bin/sbang')
    long_path = root
    while num_extend > 1:
        add = min(num_extend, 255)
        long_path = os.path.join(long_path, 'e' * add)
        num_extend -= add
    with spack.store.use_store(spack.store.Store(long_path)):
        with pytest.raises(sbang.SbangPathError) as exc_info:
            sbang.sbang_install_path()

    err = str(exc_info.value)
    assert 'root is too long' in err
    assert 'exceeds limit' in err
    assert 'cannot patch' in err
