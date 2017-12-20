# Copyright (c) Thomas Kluyver and contributors
# Distributed under the terms of the MIT license; see LICENSE file.

import os.path as osp
import pytest
import warnings

import entrypoints

samples_dir = osp.join(osp.dirname(__file__), 'samples')

sample_path = [
    osp.join(samples_dir, 'packages1'),
    osp.join(samples_dir, 'packages1', 'baz-0.3.egg'),
    osp.join(samples_dir, 'packages2'),
    osp.join(samples_dir, 'packages2', 'qux-0.4.egg'),
]

def test_get_group_all(tmpdir):
    group = entrypoints.get_group_all('entrypoints.test1', sample_path,
                                      cache_file=str(tmpdir / 'cache.json'))
    print(group)
    assert len(group) == 5
    assert set(ep.name for ep in group) == {'abc', 'rew', 'opo', 'njn'}

def test_get_group_named(tmpdir):
    group = entrypoints.get_group_named('entrypoints.test1', sample_path,
                                        cache_file=str(tmpdir / 'cache.json'))
    print(group)
    assert len(group) == 4
    assert group['abc'].module_name == 'foo'
    assert group['abc'].object_name == 'abc'

def test_get_single(tmpdir):
    ep = entrypoints.get_single('entrypoints.test1', 'abc', sample_path,
                                cache_file = str(tmpdir / 'cache.json'))
    assert ep.module_name == 'foo'
    assert ep.object_name == 'abc'

    ep2 = entrypoints.get_single('entrypoints.test1', 'njn', sample_path,
                                 cache_file=str(tmpdir / 'cache.json'))
    assert ep.module_name == 'foo'
    assert ep.object_name == 'abc'

def test_dot_prefix(tmpdir):
    ep = entrypoints.get_single('blogtool.parsers', '.rst', sample_path,
                                cache_file=str(tmpdir / 'cache.json'))
    assert ep.object_name == 'SomeClass.some_classmethod'
    assert ep.extras == ['reST']

    group = entrypoints.get_group_named('blogtool.parsers', sample_path,
                                        cache_file=str(tmpdir / 'cache.json'))
    assert set(group.keys()) == {'.rst'}

def test_case_sensitive(tmpdir):
    group = entrypoints.get_group_named('test.case_sensitive', sample_path,
                                        cache_file=str(tmpdir / 'cache.json'))
    assert set(group.keys()) == {'Ptangle', 'ptangle'}

def test_load():
    ep = entrypoints.EntryPoint('get_ep', 'entrypoints', 'get_single', None)
    obj = ep.load()
    assert obj is entrypoints.get_single

    # The object part is optional (e.g. pytest plugins use just a module ref)
    ep = entrypoints.EntryPoint('ep_mod', 'entrypoints', None)
    obj = ep.load()
    assert obj is entrypoints

def test_bad(tmpdir):
    bad_path = [osp.join(samples_dir, 'packages3')]

    group = entrypoints.get_group_named('entrypoints.test1', bad_path,
                                    cache_file=str(tmpdir / 'cache.json'))

    assert 'bad' not in group

    with pytest.raises(entrypoints.NoSuchEntryPoint):
        ep = entrypoints.get_single('entrypoints.test1', 'bad', bad_path,
                                    cache_file=str(tmpdir / 'cache.json'))

def test_missing(tmpdir):
    with pytest.raises(entrypoints.NoSuchEntryPoint) as ec:
        entrypoints.get_single('no.such.group', 'no_such_name', sample_path,
                               cache_file=str(tmpdir / 'cache.json'))

    assert ec.value.group == 'no.such.group'
    assert ec.value.name == 'no_such_name'

def test_parse():
    ep = entrypoints.EntryPoint.from_string(
        'some.module:some.attr [extra1,extra2]', 'foo'
    )
    assert ep.module_name == 'some.module'
    assert ep.object_name == 'some.attr'
    assert ep.extras == ['extra1', 'extra2']

def test_parse_bad():
    with pytest.raises(entrypoints.BadEntryPoint):
        entrypoints.EntryPoint.from_string("this won't work", 'foo')
