# -*- coding: utf-8 -*-

# Copyright: (c) 2022, Daniel Schmidt <danischm@cisco.com>

import pytest

from nexus_pcv.apic import ApicObject

pytestmark = pytest.mark.unit


@pytest.fixture
def root():
    return ApicObject("root", {}, [], None)


@pytest.fixture
def tree(root):
    root.add_child("c1_1", {"dn": "i1", "name": "n1"}, [])
    root.add_child("c1_2", {"dn": "i2", "name": "n2"}, [])
    root.add_child("c1_2", {"dn": "i3", "name": "n3"}, [])
    return root


def test_update(tree):
    tree[0].update({"new": "n1"}, [])
    assert tree[0]["new"] == "n1"
    tree[0].update({"new": "n2"}, [])
    assert tree[0]["new"] == "n2"


def test_find(tree):
    objs = tree.find(dn="i2")
    assert len(objs) == 1
    assert objs[0].cl == "c1_2"
    assert objs[0]["dn"] == "i2"
    objs = tree.find(cl="c1_2")
    assert len(objs) == 2
    objs = tree.find(dn="i2")
    assert len(objs) == 1
    objs = tree.find()
    assert len(objs) == 0
    objs = tree.find(dn="i2", cl="c1_2")
    assert len(objs) == 1


def test_insert(tree):
    tree.insert(ApicObject("c1_1", {"dn": "i1", "new": "n1"}, [], tree))
    assert tree[0]["new"] == "n1"
    tree.insert(ApicObject("c3_1", {"dn": "i1/i1/i1", "new": "n2"}, [], tree))
    assert tree[0][0][0]["new"] == "n2"
    assert tree[0][0]["dn"] == "i1/i1"
    tree.insert(ApicObject("c1_3", {"dn": "i4", "new": "n3"}, [], tree))
    assert tree[3]["new"] == "n3"
    length = len(tree.children)
    tree.insert(None)
    assert length == len(tree.children)


def test_add_child(tree):
    tree.add_child("c1_3", {"dn": "i4", "name": "n4"}, [])
    assert tree[3].cl == "c1_3"


def test_add_parent(tree):
    tree.add_parent("root_root", {})
    assert tree.parent.cl == "root_root"
    with pytest.raises(Exception):
        tree.add_parent("root2", {})


def test_get_root(tree):
    obj = tree.get_root()
    assert obj == tree
    obj = tree[0].get_root()
    assert obj == tree
    obj = ApicObject("no_root", {}, [], None).get_root()
    assert obj is None
    o = ApicObject("no_root", {}, [], None)
    o.parent = o
    obj = o.get_root()
    assert obj is None
