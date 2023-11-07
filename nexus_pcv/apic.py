# -*- coding: utf-8 -*-

# Copyright: (c) 2022, Daniel Schmidt <danischm@cisco.com>

import json
import logging
from typing import Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class ApicObject:
    def __init__(
        self,
        cl: Optional[str],
        attributes: Dict[str, str],
        children: List["ApicObject"],
        parent: Optional["ApicObject"],
    ):
        self.cl = cl
        self.attributes = attributes
        self.children = children
        self.parent = parent

    def update(
        self,
        attributes: Dict[str, str],
        children: List["ApicObject"],
    ) -> None:
        """Update object attributes, classname and children"""
        self.attributes.update(attributes)
        for child in children:
            dn = child.attributes.get("dn")
            name = child.attributes.get("name")
            found = False
            # look for existing object with dn
            if dn is not None:
                for c in self.children:
                    if c.attributes.get("dn") == dn:
                        if child.cl != c.cl:
                            continue
                        c.update(child.attributes, child.children)
                        found = True
            if found:
                continue
            # look for existing object with name
            if name is not None:
                for c in self.children:
                    if c.attributes.get("name") == name and child.cl == c.cl:
                        c.update(child.attributes, child.children)
                        found = True
            if found:
                continue
            # add as a new child
            self.children.append(
                ApicObject(child.cl, child.attributes, child.children, self)
            )

    def find(self, dn: str = "", cl: str = "") -> List["ApicObject"]:
        """Find objects by dn or classname in subtree"""
        result: List["ApicObject"] = []
        if not dn and not cl:
            return result
        elif not cl:
            if self.attributes.get("dn") == dn:
                result.append(self)
        elif not dn:
            if self.cl == cl:
                result.append(self)
        elif self.attributes.get("dn") == dn and self.cl == cl:
            result.append(self)
        for child in self.children:
            objs = child.find(dn=dn, cl=cl)
            result.extend(objs)
        return result

    def _index_of_last_dn_delimiter(self, dn: str) -> int:
        """Helper function to return index of last delimiter ('/') in DN string"""
        escaped = 0
        index = len(dn) - 1
        for c in reversed(dn):
            if c == "]":
                escaped += 1
            elif c == "[":
                escaped -= 1
            elif c == "/" and escaped == 0:
                return index
            index -= 1
        return -1

    def insert(self, obj: Optional["ApicObject"]) -> None:
        """Insert object in correct place in tree according to dn"""
        if obj is None:
            return
        dn = obj.attributes["dn"]
        o = self.find(dn=dn)
        if len(o) > 0:
            o[0].update(obj.attributes, obj.children)
        else:
            index = self._index_of_last_dn_delimiter(dn)
            if index == -1:
                self.children.append(obj)
                obj.parent = self
            else:
                parent_dn = dn[:index]
                o = self.find(dn=parent_dn)
                if len(o) > 0:
                    o[0].children.append(obj)
                    obj.parent = o[0]
                else:
                    new_obj = ApicObject(None, {"dn": parent_dn}, [obj], None)
                    obj.parent = new_obj
                    self.insert(new_obj)

    def add_child(
        self, cl: str, attributes: Dict[str, str], children: List["ApicObject"]
    ) -> "ApicObject":
        """Add child to object"""
        child = ApicObject(cl, attributes, children, self)
        self.children.append(child)
        return child

    def add_parent(self, cl: str, attributes: Dict[str, str]) -> "ApicObject":
        """Add parent to object"""
        if self.parent is not None:
            raise Exception(
                "ApicObject {} already has a parent.".format(str(ApicObject))
            )
        self.parent = ApicObject(cl, attributes, [self], None)
        return self.parent

    def get_root(self) -> Optional["ApicObject"]:
        """Get root object"""
        obj = self
        # max search depth 100
        for i in range(100):
            if obj.cl == "root":
                return obj
            elif obj.parent is not None:
                obj = obj.parent
            else:
                return None
        return None

    def __getitem__(self, key: Union[str, int]) -> Union["ApicObject", str, None]:
        """Get attribute if key is string otherwise child by index"""
        if isinstance(key, str):
            return self.attributes.get(key)
        else:
            return self.children[key]

    def __str__(self) -> str:
        """Return json string."""
        attr_string = ", ".join(
            ['"{}": {}'.format(k, json.dumps(v)) for k, v in self.attributes.items()]
        )
        child_string = ", ".join([str(c) for c in self.children])
        return '{{"{}": {{"attributes": {{{}}}, "children": [{}]}}}}'.format(
            self.cl, attr_string, child_string
        )
