import os.path as osp
import shutil
from testpath import assert_isfile, assert_not_path_exists, modified_env
from .test_entrypoints import temp_cache_file

import entrypoints

samples_dir = osp.join(osp.dirname(__file__), 'samples')
sample_pkgs_1 = osp.join(samples_dir, 'packages1')
sample_path = [
    sample_pkgs_1,
    osp.join(samples_dir, 'packages1', 'baz-0.3.egg'),
    osp.join(samples_dir, 'packages2'),
    osp.join(samples_dir, 'packages2', 'qux-0.4.egg'),
]

def test_using_cache(temp_cache_file, tmpdir):
    assert_not_path_exists(temp_cache_file)
    test_pkg_dir = str(tmpdir / 'packages1')
    shutil.copytree(sample_pkgs_1, test_pkg_dir)

    ep = entrypoints.get_single('entrypoints.test1', 'abc', [test_pkg_dir])
    assert ep.module_name == 'foo'
    assert_isfile(temp_cache_file)

    # Now modify it
    with open(osp.join(test_pkg_dir, 'foo-0.1.dist-info', 'entry_points.txt'), 'w') as f:
        f.write("[entrypoints.test1]\n")
        f.write("abc = oof:abc")

    # At this point it should still use the cache
    ep = entrypoints.get_single('entrypoints.test1', 'abc', [test_pkg_dir])
    assert ep.module_name == 'foo'

    with open(osp.join(test_pkg_dir, 'touched'), 'w'):
        pass

    # Now the directory mtime should be changed, so it should refresh the cache.
    ep = entrypoints.get_single('entrypoints.test1', 'abc', [test_pkg_dir])
    assert ep.module_name == 'oof'

def test_cache_disabled(tmpdir):
    test_pkg_dir = str(tmpdir / 'packages1')
    shutil.copytree(sample_pkgs_1, test_pkg_dir)

    with modified_env({'ENTRYPOINTS_CACHE_FILE': '0'}):
        ep = entrypoints.get_single('entrypoints.test1', 'abc', [test_pkg_dir])
        assert ep.module_name == 'foo'

        # Now modify it
        with open(osp.join(test_pkg_dir, 'foo-0.1.dist-info', 'entry_points.txt'), 'w') as f:
            f.write("[entrypoints.test1]\n")
            f.write("abc = oof:abc")

        # With no cache file, the change should show up immediately
        ep = entrypoints.get_single('entrypoints.test1', 'abc', [test_pkg_dir])
        assert ep.module_name == 'oof'
