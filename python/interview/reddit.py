
from collections import OrderedDict, deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable
import asyncio
import bisect
import heapq
import json
import pytest
import re
import sys
import time

import pymemcache.client.base as pymemcache

class ConsistentHash:

    hash_fn: Callable[[str], int]
    num_virtual: int
    node_locs: list[int] = []
    node_names: dict[int, str] = {}

    def __init__(self, *, num_virtual:int=3, hash_fn=hash):
        self.num_virtual = num_virtual
        self.hash_fn = hash_fn


    def add_node(self, name: str):
        for i in range(self.num_virtual):
            loc = self.hash_fn(f"{name}.{i}")
            self.node_names[loc] = name
            bisect.insort(self.node_locs, loc)
        
        
    def remove_node(self, name: str):
        for i in range(self.num_virtual):
            loc = self.hash_fn(f"{name}.{i}")
            loc_i = bisect.bisect_left(self.node_locs, loc)
            if self.node_locs[loc_i] != loc:
                raise ValueError(f"Unable to find node '{name}' in the hash ring")
            self.node_locs.pop(loc_i)
            self.node_names.pop(loc)

        # warm the cache in the next node?
        
    def get_node(self, key: str):
        key_loc = self.hash_fn(key)
        loc_i = bisect.bisect_left(self.node_locs, key_loc)
        if loc_i < len(self.node_locs):
            loc = self.node_locs[loc_i]
        else:
            loc = self.node_locs[0]
        assert loc in self.node_names, f"expected node location {loc} to exist in node_names, but it did not"
            
        return self.node_names[loc]        
    
    @staticmethod
    def run_consistent_hash_tests():
        stable_hash: Callable[[str], int] = lambda value: {
                "a.0": 10,
                "a.1": 50,
                "a.2": 90,
                "b.0": 20,
                "b.1": 60,
                "b.2": 100,
                "user:1": 45,
                "user:2": 20,
                "user:3": 120,
            }[value]
    
        ch = ConsistentHash(num_virtual=3, hash_fn=stable_hash)
        ch.add_node("a")
        a0_loc_actual = ch.node_locs[0]
        assert a0_loc_actual == 10, f"expected ch.node_locs[0] = 10, got {a0_loc_actual}"
        assert ch.node_names[10] == "a", f"expected ch.node_names[10] = 'a.0', got {ch.node_names[10]}"
        ch.add_node("b")
        b2_loc_actual = ch.node_locs[1]
        assert b2_loc_actual == 20, f"expected ch.node_locs[1] = 20, got {b2_loc_actual}"
        assert ch.node_names[100] == "b", f"expected ch.node_names[100] = 'b.2', got {ch.node_names[100]}"

        user1_actual = ch.get_node("user:1")
        assert user1_actual == "a", f"expected ch.get_node('user:1') = 'a', got {user1_actual}"
        user2_actual = ch.get_node("user:2")
        assert user2_actual == "b", f"expected ch.get_node('user:2') = 'b', got {user2_actual}"
        user3_actual = ch.get_node("user:3")
        assert user3_actual == "a", f"expected ch.get_node('user:3') = 'a', got {user3_actual}"
        
        ch.remove_node("a")
        assert len(ch.node_locs) == 3, f"expected after remove_node('a') for len(ch.node_locs) == 3, got {len(ch.node_locs)}"

        user1_rm_actual = ch.get_node("user:1")
        assert user1_rm_actual == "b", f"expected after removing a ch.get_node('user:1') = 'b', got {user1_rm_actual}"

        print("Success")
        
        
        
class ConsistentHash2:
    
    def __init__(self, virtual_nodes: int = 3, hasher: Callable[[str],int] = hash):
        self.nodes = [] # hosts, sorted by hash value
        self.virtual_nodes = virtual_nodes
        self.hasher = hasher
    
    def add_node(self, hostname: str):
        for v in range(self.virtual_nodes):
            bisect.insort(self.nodes, (self.hasher(f"{hostname}.{v}"), hostname), key=lambda t: t[0])
        
    def remove_node(self, hostname: str):
        
        for v in range(self.virtual_nodes):
            host_index = bisect.bisect_left(self.nodes, self.hasher(f"{hostname}.{v}"), key=lambda t: t[0])
            if self.nodes[host_index][1] != hostname:
                raise ValueError(f"remove_node({hostname}) expected to find entry for virtual node {v}, but did not")
            
            self.nodes.pop(host_index)
        
    def get_node(self, id: str) -> str:
        id_hash = self.hasher(id)
        id_host = bisect.bisect_left(self.nodes, id_hash, key=lambda t: t[0])
        if id_host < len(self.nodes):
            return self.nodes[id_host][1]
        else:
            return self.nodes[0][1]
        
    @staticmethod
    def run_tests():
        stable_hash: Callable[[str], int] = lambda value: {
                "a.0": 10,
                "a.1": 50,
                "a.2": 90,
                "b.0": 20,
                "b.1": 60,
                "b.2": 100,
                "user:1": 45,
                "user:2": 20,
                "user:3": 120,
            }[value]
    
        ch = ConsistentHash2(hasher=stable_hash)
        ch.add_node("a")
        ch.add_node("b")
        assert ch.nodes == [
            (10, "a"),
            (20, "b"),
            (50, "a"),
            (60, "b"),
            (90, "a"),
            (100, "b"),
        ], f"unexpected ch.nodes structure: {ch.nodes}"

        user1_actual = ch.get_node("user:1")
        assert user1_actual == "a", f"expected ch.get_node('user:1') = 'a', got {user1_actual}"
        user2_actual = ch.get_node("user:2")
        assert user2_actual == "b", f"expected ch.get_node('user:2') = 'b', got {user2_actual}"
        user3_actual = ch.get_node("user:3")
        assert user3_actual == "a", f"expected ch.get_node('user:3') = 'a', got {user3_actual}"
        
        ch.remove_node("a")
        assert len(ch.nodes) == 3, f"expected after remove_node('a') for len(ch.nodes) == 3, got {len(ch.nodes)}"

        user1_rm_actual = ch.get_node("user:1")
        assert user1_rm_actual == "b", f"expected after removing a ch.get_node('user:1') = 'b', got {user1_rm_actual}"

        print("ConsistentHash2.run_tests() - Success")   
        

def run_lru_tests(make_cache: Callable[[], object]):
    s1 = make_cache()
    s1.put("one", 1)
    s1.put("two", 2)
    s1.put("three", 3)
    s1.put("four", 4)
    
    s1_three_actual = s1.get("three")
    assert s1_three_actual == 3, f"expected s1.get('three') == 3, got {s1_three_actual}"
    s1.get("two")
    s1_two_actual = s1.get("two")
    assert s1_two_actual == 2, f"expected s1.get('two') == 2, got {s1_two_actual}"

    assert len(s1.cache) == 4, f"expected len(s1.cache) == 4, got {len(s1.cache)}"
    assert s1.first() == "two", f"expected first() == 'two', got {s1.first()}"
    assert s1.last() == "one", f"expected last() == 'one', got {s1.last()}"

    s1.put("five", 5)
    
    assert len(s1.cache) == 4, f"expected len(s1.cache) == 4, got {len(s1.cache)}"
    s1_expected_keys = {"two", "three", "four", "five"}
    s1_actual_keys = {k for k in s1.cache}
    assert s1_actual_keys == s1_expected_keys, f"expected s1.cache keys {s1_expected_keys}, got {s1_actual_keys}"
    assert s1.first() == "five", f"expected first() == 'five', got {s1.first()}"
    assert s1.last() == "four", f"expected last() == 'four', got {s1.last()}"

    # Regression: duplicate insert should not leave stale node references behind.
    s2 = make_cache()
    s2.put("a", 1)
    s2.put("a", 2)
    assert len(s2.cache) == 1, f"expected len(s2.cache) == 1, got {len(s2.cache)}"
    assert s2.first() == "a", f"expected first() == 'a', got {s2.first()}"
    assert s2.last() == "a", f"expected last() == 'a', got {s2.last()}"

    # Regression: single-item access should remain consistent.
    s3 = make_cache()
    s3.put("x", 10)
    assert s3.get("x") == 10, f"expected s3.get('x') == 10, got {s3.get('x')}"
    assert s3.first() == "x", f"expected first() == 'x', got {s3.first()}"
    assert s3.last() == "x", f"expected last() == 'x', got {s3.last()}"

    # Regression: eviction order should keep the least-recently-used item at the tail
    # of the doubly-linked list, not necessarily in the dict's insertion order.
    s4 = make_cache()
    for key in ["a", "b", "c", "d"]:
        s4.put(key, ord(key))
    s4.get("b")
    s4.put("e", 69)

    seen = []
    node = s4.head if hasattr(s4, "head") else None
    if node is not None:
        while node is not None:
            seen.append(node.key)
            node = node.next
    else:
        seen = list(s4.cache.keys())

    assert seen == ["e", "b", "d", "c"], f"expected LRU order ['e', 'b', 'd', 'c'], got {seen}"
    assert s4.last() == "c", f"expected last() == 'c', got {s4.last()}"
    
    print("Success")

@dataclass
class LruCache[K, V]:
    
    @dataclass
    class _LruItem:
        key: K
        val: V
        prev = None
        next = None
        
    head: _LruItem = None
    tail: _LruItem = None
    cache: dict[K, _LruItem] = field(default_factory=dict)
    capacity: int = 4
    
    
    def _evict_tail(self):
        
        if self.tail is None:
            return
        
        evicted = self.tail
        self.cache.pop(evicted.key, None)
        
        if evicted.prev is None:
            self.head = None
            self.tail = None
            return
        
        self.tail.prev.next = None
        self.tail = evicted.prev
        
        
    def _move_to_head(self, item: _LruItem):
        
        if self.head is item:
            return
    
        if self.tail is item:
            self.tail = item.prev
            self.tail.next = None
        else:
            item.next.prev = item.prev
        item.prev.next = item.next
        item.prev = None
        item.next = self.head
        self.head.prev = item
        self.head = item
        
    
    def put(self, key: K, value: V):
        
        item: LruCache._LruItem = None
        if key in self.cache:
            item = self.cache[key]
            item.val = value
        else:
            item = self._LruItem(key, value)
            self.cache[key] = item    
        
        if self.head is None:
            self.head = item
            self.tail = item
        else:
            item.next = self.head
            self.head.prev = item
            self.head = item
            
        while len(self.cache) > self.capacity:
            self._evict_tail()            
            
    
    def get(self, key: K) -> V:
        
        if key not in self.cache:
            raise ValueError(f"no key {key} found in the cache")
        
        item = self.cache[key]
        self._move_to_head(item)        
        return item.val

    def first(self):
        if self.head is None:
            raise ValueError("cache is empty")
        return self.head.key

    def last(self):
        if self.tail is None:
            raise ValueError("cache is empty")
        return self.tail.key
    
    @classmethod
    def run_tests(cls):
        run_lru_tests(cls)

        

class LruCacheOrderedDict[K, V]:
    def __init__(self, capacity: int = 4):
        self.capacity = capacity
        self.cache: OrderedDict[K, V] = OrderedDict()

    def put(self, key: K, value: V):
        if key in self.cache:
            del self.cache[key]

        self.cache[key] = value

        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def get(self, key: K) -> V:
        if key not in self.cache:
            raise ValueError(f"no key {key} found in the cache")

        value = self.cache.pop(key)
        self.cache[key] = value
        return value

    def first(self):
        if not self.cache:
            raise ValueError("cache is empty")
        return next(reversed(self.cache))

    def last(self):
        if not self.cache:
            raise ValueError("cache is empty")
        return next(iter(self.cache))

    @classmethod
    def run_tests(cls):
        run_lru_tests(cls)


class SingleLinkedList[V]:
    
    @dataclass
    class _Node:
        data: V
        next: SingleLinkedList._Node[V] | None = None
    
    def __init__(self):
        self.head: SingleLinkedList._Node | None = None
        self.tail: SingleLinkedList._Node | None = None
        
    def insert(self, val: V, index: int = 0):
        new = self._Node(val)
        
        if self.head is None:
            if index != 0:
                raise ValueError(f"Invalid insert index {index} for empty list")
            self.head = new
            self.tail = new
            return

        if index == 0:
            new.next = self.head
            self.head = new
            return

        cur = self._node_before(index)

        if cur.next is None:
            self.tail.next = new
            self.tail = self.tail.next
        else:
            new.next = cur.next
            cur.next = new
        
    def delete(self, index: int) -> V:
        if self.head is None:
            raise ValueError(f"delete({index}) called on an empty list")
        
        if index == 0:
            deleted = self.head
            self.head = self.head.next
            return deleted
        
        cur = self._node_before(index)
        
        deleted = cur.next
        if deleted == self.tail:
            self.tail = cur
            cur.next = None
        else:
            cur.next = deleted.next
        
        return deleted.data

    
    def _node_before(self, index: int) -> SingleLinkedList._Node:
        if self.head is None:
            raise ValueError(f"_node_before index {index} called on an empty list")
        
        if index < 1:
            raise ValueError(f"_node_before invalid index {index}")
       
        cur = self.head
        for i in range(index-1):
            if cur.next is None and i < (index-1):
                raise ValueError(f"_node_before index {index} called on list with length {i+1}")
            else:
                cur = cur.next

        return cur
    
    
    @staticmethod
    def run_tests():
        l1 = SingleLinkedList[int]()
        l1.insert(3)
        l1.insert(2)
        l1.insert(1)
        l1.insert(0)
        
        with pytest.raises(ValueError):
            SingleLinkedList[int]()._node_before(0)
        with pytest.raises(ValueError):
            l1._node_before(0)
        with pytest.raises(ValueError):
            l1._node_before(5)

        actual = l1._node_before(1).data
        assert actual == 0, f"Expected l1._node_before(1).data == 0, got {actual}"
        actual = l1._node_before(2).data
        assert actual == 1, f"Expected l1._node_before(2).data == 1, got {actual}"
        actual = l1._node_before(3).data
        assert actual == 2, f"Expected l1._node_before(3).data == 2, got {actual}"
        actual = l1._node_before(4).data
        assert actual == 3, f"Expected l1._node_before(4).data == 3, got {actual}"
        
        
class BinaryTree[V]:
    
    @dataclass
    class _Node:
        data: V
        left: BinaryTree._Node | None = None
        right: BinaryTree._Node | None = None
        
    def __init__(self, key=None):
        self.head: self._Node | None = None
        self.key = key if key is not None else (lambda x: x)
        
    def insert(self, val: V):
        
        if self.head is None:
            self.head = self._Node(val)
            return
        
        def _insert_val(node):
            if val < self.key(node.data):
                if node.left is None:
                    node.left = self._Node(val)
                else:
                    _insert_val(node.left)
            else:
                if node.right is None:
                    node.right = self._Node(val)
                else:
                    _insert_val(node.right)
        
        _insert_val(self.head)
        
    def search(self, val: V) -> V | None:
        
        if self.head is None:
            return None
        
        def _find_val(node) -> V | None:
            if node is None:
                return None
            if val == node.data:
                return node.data
            if val < node.data:
                return _find_val(node.left)
            else:
                return _find_val(node.right)
            
        return _find_val(self.head)
    
    def serialize(self) -> list[V]:
        
        def _ser(node: BinaryTree._Node):
            if node.left is None and node.right is None:
                return f"{node.data},"
            elif node.right is None:
                return f"{node.data},{_ser(node.left)}"
            elif node.left is None:
                return f"{node.data},{_ser(node.right)}"
            else:
                return f"{node.data},{_ser(node.left)}{_ser(node.right)}"            
        
        return _ser(self.head).rstrip(",")
        
    @staticmethod
    def deserialize[V](input: str, data_parser: Callable[[str],V]) -> BinaryTree[V]:
        
        tree = BinaryTree[V]()
        for s in input.split(","):
            tree.insert(data_parser(s))
        return tree        

    @staticmethod
    def run_tests():
        b1 = BinaryTree[int]()
        b1.insert(3)
        b1.insert(1)
        b1.insert(0)
        b1.insert(2)
        b1.insert(5)
        b1.insert(6)

        actual, expected = b1.search(0), 0
        assert actual == expected, f"expected b1.search({expected}) == {expected}, got {actual}"
        actual, expected = b1.search(1), 1
        assert actual == expected, f"expected b1.search({expected}) == {expected}, got {actual}"
        actual, expected = b1.search(2), 2
        assert actual == expected, f"expected b1.search({expected}) == {expected}, got {actual}"
        actual, expected = b1.search(5), 5
        assert actual == expected, f"expected b1.search({expected}) == {expected}, got {actual}"
        actual, expected = b1.search(4), None
        assert actual == expected, f"expected b1.search({expected}) == {expected}, got {actual}"
        
        actual, expected = b1.serialize(), "3,1,0,2,5,6"
        assert actual == expected, f"b1.serialize() = {actual}, expected {expected}"
        
        actual, expected = BinaryTree[int].deserialize("3,1,0,2,5,6", data_parser=(lambda s: int(s))).serialize(), "3,1,0,2,5,6"
        assert actual == expected, f"deserialize().serialize() = {actual}, expected {expected}"
        
        print("SUCCESS")


class HashTable[K,V]:
        
    def __init__(self, capacity=17):
        self.capacity: int = capacity
        self.table: list[list[tuple[K,V]]] = [[] for _ in range(self.capacity)]
        
    def put(self, key: K, val: V):
        index = hash(key) % self.capacity
        subindex = bisect.bisect_left(self.table[index], key, key=lambda t: t[0])
        
        if subindex < len(self.table[index]) and self.table[index][subindex][0] == key:
            self.table[index][subindex] = (key, val)
        else:
            bisect.insort(self.table[index], (key, val))

    def get(self, key: K) -> V | None:
        index = hash(key) % self.capacity
        subindex = bisect.bisect_left(self.table[index], key, key=lambda t: t[0])
        
        if subindex < len(self.table[index]) and self.table[index][subindex][0] == key:
            return self.table[index][subindex][1]
        else:
            return None
        
    @staticmethod
    def run_tests():
        ht1 = HashTable[str,str](3)
        
        ht1.put("one", "1")
        ht1.put("two", "2")
        ht1.put("three", "3")
        ht1.put("four", "4")
        ht1.put("five", "5")
        ht1.put("six", "6")
        ht1.put("seven", "7")
        ht1.put("eight", "8")
        ht1.put("nine", "99")
        ht1.put("nine", "9")
        
        actual, expected = ht1.get("three"), "3"
        assert actual == expected, f"hg1.get('three') = {actual}, expected {expected}"
        actual, expected = ht1.get("eight"), "8"
        assert actual == expected, f"hg1.get('eight') = {actual}, expected {expected}"
        actual, expected = ht1.get("nine"), "9"
        assert actual == expected, f"hg1.get('nine') = {actual}, expected {expected}"
        actual, expected = ht1.get("ten"), None
        assert actual == expected, f"hg1.get('ten') = {actual}, expected {expected}"

        print("HashTable.run_tests() - SUCCESS")
        

def test_core_structures():
    
    odict = OrderedDict[str, int]()
    odict["one"] = 1
    odict["two"] = 2
    odict["three"] = 3
    odict["four"] = 4
    
    actual, expected = [k for k in odict.keys()], ["one", "two", "three", "four"]
    assert actual == expected, f"odict keys = {actual}, expected {expected}"
    actual, expected = [k for k in odict.values()], [1, 2, 3, 4]
    assert actual == expected, f"odict values = {actual}, expected {expected}"
    
    deq = deque()
    deq.append(2)
    deq.append(3)
    deq.append(4)
    deq.appendleft(1)
    deq.appendleft(0)
    
    actual, expected = [v for v in deq], [0, 1, 2, 3, 4]
    assert actual == expected, f"deq values = {actual}, expected {expected}"

    actual, expected = deq.pop(), 4
    assert actual == expected, f"deq.pop() = {actual}, expected {expected}"
    actual, expected = deq.popleft(), 0
    assert actual == expected, f"deq.pop() = {actual}, expected {expected}"
    actual, expected = len(deq), 3
    assert actual == expected, f"len(deq) = {actual}, expected {expected}"
    
    print ("test_core_structures - SUCCESS")


class DLinkedList[V]:
    
    @dataclass
    class _Item:
        data: V
        prev: DLinkedList._Item | None = None
        next: DLinkedList._Item | None = None
        
        def pr(self):
            print(f"_Item[data: {self.data}, prev: {"None" if self.prev is None else self.prev.data}, next: {"None" if self.next is None else self.next.data}]")
        
    def __init__(self):
        self.head: self._Item | None = None
        self.tail: self._Item | None = None
        
    def _pr_list(self):
        cur = self.head
        while cur is not None:
            cur.pr()
            cur = cur.next
        
    def _item_before(self, index: int) -> DLinkedList._Item | None:
        if self.head is None:
            return None
        
        cur = self.head
        for i in range(index-1):
            if cur.next is None and i < (index-1):
                raise ValueError(f"error finding value before index {index} in list length {i+1}")
            cur = cur.next
            
        return cur
    
    def insert(self, val: V, index: int):
        if self.head is None:
            self.head = self._Item(val)
            self.tail = self.head
            return
        
        if index == 0:
            item = self._Item(val)
            item.next = self.head
            self.head.prev = item
            self.head = item
            return
        
        before = self._item_before(index)
        item = self._Item(val)
        item.prev = before
        item.next = before.next
        before.next = item
        if self.tail == before:
            self.tail = item
        else:
            item.next.prev = item
            
        print(f"LIST[head: {self.head.data}, tail: {self.tail.data}]:")
        self._pr_list()
        
    def get(self, index: int) -> V | None:
        if self.head is None:
            return None
        
        if index == 0:
            return self.head.data
        
        before = self._item_before(index)
        if before is not None and before.next is not None:
            return before.next.data
        return None
    
    def delete(self, index: int) -> V | None:
        if self.head is None:
            return None
        
        if index == 0:
            deleted = self.head
            self.head = self.head.next
            self.head.prev = None
            return deleted.data
        
        before = self._item_before(index)
        if before is None or before.next is None:
            return None
        
        deleted = before.next
        before.next = deleted.next
        if deleted.next is None:
            self.tail = before
        else:
            deleted.next.prev = before
            
        return deleted.data
    

    @staticmethod
    def run_tests():
        dll1 = DLinkedList[int]()
        dll1.insert(1, 0)
        dll1.insert(0, 0)
        dll1.insert(2, 2)
        dll1.insert(4, 3)
        dll1.insert(3, 3)
        
        actual, expected = dll1.get(0), 0
        assert actual == expected, f"dll1.get(0) = {actual}, expected {expected}"
        actual, expected = dll1.get(4), 4
        assert actual == expected, f"dll1.get(4) = {actual}, expected {expected}"
        actual, expected = dll1.get(2), 2
        assert actual == expected, f"dll1.get(2) = {actual}, expected {expected}"
        actual, expected = dll1.get(5), None
        assert actual == expected, f"dll1.get(5) = {actual}, expected {expected}"

        actual, expected = dll1.delete(4), 4
        assert actual == expected, f"dll1.delete(4) = {actual}, expected {expected}"
        actual, expected = dll1.delete(0), 0
        assert actual == expected, f"dll1.delete(0) = {actual}, expected {expected}"
        actual, expected = dll1.delete(1), 2
        assert actual == expected, f"dll1.delete(1) = {actual}, expected {expected}"

        print("DLinkedList.run_tests() - SUCCESS")
        
        
class LfuCache[K,V]:
    
    @dataclass
    class _Item:
        key: K
        val: V
        count: int = 0
        prev: LfuCache._Item = None
        next: LfuCache._Item = None
    
    def __init__(self, size=10):
        self.cache: dict[K,LfuCache._Item] = {}
        self.head: LfuCache._Item = None
        self.tail: LfuCache._Item = None
        self.size = size
        
    def _print_list(self):
        cur = self.head
        while cur is not None:
            print(f"_Item[key: {cur.key}, val: {cur.val}, count: {cur.count}, prevkey: {None if cur.prev is None else cur.prev.key}, nextkey: {None if cur.next is None else cur.next.key}]")
            cur = cur.next
        print(f"_Item TAIL[key: {self.tail.key}, val: {self.tail.val}, count: {self.tail.count}, prevkey: {None if self.tail.prev is None else self.tail.prev.key}, nextkey: {None if self.tail.next is None else self.tail.next.key}]")
        
    def get(self, key: K) -> V | None:
        if key not in self.cache:
            return None
        
        item = self.cache[key]
        item.count += 1
        while item.prev is not None and item.count > item.prev.count:
            if item.next is not None:
                item.next.prev = item.prev
            item.prev.next = item.next

            if self.tail == item:
                self.tail = item.prev                
            
            item.next = item.prev
            item.prev.prev = item
            if item.prev == self.head:
                self.head = item
                item.prev = None
            else:
                new_prev = item.prev.prev
                new_prev.next = item
                item.prev = new_prev
        
            print(f"get({key}) iteration items:")
            self._print_list()
            print()
        
        return item.val
    
    def put(self, key: K, val: V):
        
        if key in self.cache:
            item = self.cache[key]
            item.val = val
            return

        item = self._Item(key, val)
        self.cache[key] = item

        if len(self.cache) > self.size:
            self.cache.pop(self.tail.key)
            self.tail.prev.next = None
            self.tail = self.tail.prev

        if self.head is None:
            self.head = item
            self.tail = item

        else:
            self.tail.next = item
            item.prev = self.tail
            self.tail = item
            
        print(f"put({key}, {val}) items:")
        self._print_list()
        print()
       
       
    @staticmethod
    def run_tests():
        lfu1 = LfuCache[str,str](size=3)
        lfu1.put("one", "1")
        lfu1.put("two", "2")
        lfu1.put("three", "3")
        
        actual, expected = lfu1.get("two"), "2"
        assert actual == expected, f"lfu1.get('two') == {actual}, expected {expected}"
        assert lfu1.head.key == "two", f"lfu1.head == {lfu1.head.key}, expected 'two'"
        assert lfu1.tail.key == "three", f"lfu1.tail == {lfu1.tail.key}, expected 'three'"
        
        actual, expected = lfu1.get("two"), "2"
        assert actual == expected, f"lfu1.get('two') == {actual}, expected {expected}"
        assert lfu1.head.count == 2, f"lfu1.head.count == {lfu1.head.count}, expected 2"

        lfu1.put("four", "4")        
        assert lfu1.head.key == "two", f"lfu1.head == {lfu1.head.key}, expected 'two'"
        assert lfu1.tail.key == "four", f"lfu1.tail == {lfu1.tail.key}, expected 'four'"
        
        print("LfuCache tests - SUCCESS")

    
class _MemcachedJsonSerde(object):
    """_summary_
    see: https://pymemcache.readthedocs.io/en/latest/getting_started.html#serialization
    """
    def serialize(self, key, value):
        if isinstance(value, str):
            return value.encode('utf-8'), 1
        return json.dumps(value).encode('utf-8'), 2

    def deserialize(self, key, value, flags):
        if flags == 1:
            return value.decode('utf-8')
        if flags == 2:
            return json.loads(value.decode('utf-8'))
        raise Exception("Unknown serialization format")


class TokenBucketLimiter:
    
    _DEBUG = True
    
    def __init__(self, client, identifier: str, max_tokens: float, refresh_rate: float):
        self.client = client
        self.identifier = identifier
        self.refresh_rate = refresh_rate
        self.max_tokens = max_tokens
        
    def allow_request(self, key: str, cost: float, max_retries: int = 5) -> bool:
        
        cache_key = f"{self.identifier}:{key}"
        now = time.time()

        for _ in range(max_retries):

            if self._DEBUG: print(f"allow_request(cache_key: {cache_key}, now: {now})")

            result = self.client.gets(cache_key)
            if result[0] is None:
                new_bucket = {"tokens": self.max_tokens - cost, "last_updated": now}
                if self.client.add(cache_key, new_bucket):
                    print(f"allow_request(cache_key: {cache_key}, bucket: {new_bucket}) - created")
                    return True
                continue
            
            bucket, cas_token = result
            
            elapsed = now - bucket["last_updated"]
            bucket["tokens"] = min(self.max_tokens, bucket["tokens"] + (elapsed * self.refresh_rate))
            if self._DEBUG: print(f"allow_request(cache_key: {cache_key}, bucket: {bucket}) - updating with elapsed: {elapsed}")
            if cost > bucket["tokens"]:
                if self.client.cas(cache_key, bucket, cas_token):
                    if self._DEBUG: print(f"allow_request(cache_key: {cache_key}, bucket: {bucket}) - over budget - cost: {cost} > tokens: {bucket["tokens"]}")
                    return False
                continue
            
            new_bucket = {"tokens": bucket["tokens"] - cost, "last_updated": now}
            if self.client.cas(cache_key, new_bucket, cas_token):
                if self._DEBUG: print(f"allow_request(cache_key: {cache_key}, bucket: {new_bucket}) - allowing")                
                return True
            
        if self._DEBUG: print(f"allow_request(cache_key: {cache_key}) - failing out")                
        return False

    
    @staticmethod
    async def run_tests():
        client = pymemcache.Client("127.0.0.1:11211", serde=_MemcachedJsonSerde())
        
        client.delete("TBL1:rpc1")
        client.delete("TBL1:rpc2")
        tbl1 = TokenBucketLimiter(
            client=client,
            identifier="TBL1",
            max_tokens=3,
            refresh_rate=6,
        )
        actual, expected = tbl1.allow_request("rpc1", 1), True
        assert actual == expected, f"tbl1.allow_request(rpc1, 1) == {actual}, expected {expected}"
        actual, expected = tbl1.allow_request("rpc1", 1), True
        assert actual == expected, f"tbl1.allow_request(rpc1, 1) == {actual}, expected {expected}"
        actual, expected = tbl1.allow_request("rpc1", 1), True
        assert actual == expected, f"tbl1.allow_request(rpc1, 1) == {actual}, expected {expected}"
        actual, expected = tbl1.allow_request("rpc1", 1), False
        assert actual == expected, f"tbl1.allow_request(rpc1, 1) == {actual}, expected {expected}"
        actual, expected = tbl1.allow_request("rpc2", 3), True
        assert actual == expected, f"tbl1.allow_request(rpc2, 3) == {actual}, expected {expected}"
        
        print("TokenBucketLimiter - Starting sleep...")
        await asyncio.sleep(0.5)
        print("TokenBucketLimiter - ... sleep complete")
        
        actual, expected = tbl1.allow_request("rpc1", 3), True
        assert actual == expected, f"tbl1.allow_request(rpc1, 3) == {actual}, expected {expected}"
        
        print("TokenBucketLimiter - SUCCESS")
        
        # one-liner to print stats:
        #  print(json.dumps({k.decode('utf-8'): v.decode('utf-8') if isinstance(v, bytes) else v for k,v in client.stats().items()}, indent=2))


class MergeSortedLists[V]:
    
    @staticmethod
    def merge_pairwise(lists: list[deque[V]]) -> deque[V]:
        if len(lists) < 1:
            return []
        
        def _merge2(d1, d2) -> deque[V]:
            result = deque()

            while len(d1) > 0 or len(d2) > 0:
                if len(d1) == 0:
                    for i in d2: result.append(i)
                    return result
                if len(d2) == 0:
                    for i in d1: result.append(i)
                    return result
                
                if d1[0] < d2[0]:
                    result.append(d1.popleft())
                else:
                    result.append(d2.popleft())
                    
            return result
    
        def _merges(mlists) -> list[deque[V]]:
            if len(mlists) == 1:
                return mlists
            
            merged = []
            for i in range(0, len(mlists), 2):
                if i < len(lists) - 1:
                    merged.append(_merge2(mlists[i], mlists[i+1]))
                else:
                    merged.append(mlists[i])
            return _merges(merged)

        result = _merges(lists)
        return list(result[0])
            
    @staticmethod
    def merge_heap(input: list[list[int]]) -> list[int]:
        
        heap = []
        for l in range(len(input)):
            if len(input[l]) > 0:
                heapq.heappush(heap, (input[l][0], l, 0))
                
        result = []
        while heap:
            nextmin, l, i = heapq.heappop(heap)
            result.append(nextmin)
            
            if i < len(input[l]) - 1:
                heapq.heappush(heap, (input[l][i+1], l, i+1))
        
        return result        
            
    
    @staticmethod
    def run_tests():
        # lists1 = [
        #     deque([1, 3, 5]),
        #     deque([1, 2, 6]),
        #     deque([2, 3, 4]),
        # ]
        # actual, expected = MergeSortedLists.merge_pairwise(lists1), [1, 1, 2, 2, 3, 3, 4, 5, 6]
        # assert actual == expected, f"merge_pairwise(lists1) = {actual}, expected {expected}"
        
        lists2 = [
            [1, 3, 5],
            [1, 2, 6, 7],
            [2, 3, 4],
            [],
        ]
        actual, expected = MergeSortedLists.merge_heap(lists2), [1, 1, 2, 2, 3, 3, 4, 5, 6, 7]
        assert actual == expected, f"merge_heap(lists2) = {actual}, expected {expected}"
        
        print("MergeSortedLists run_tests() - SUCCESS")

class PowerSubsets:
    
    @staticmethod
    def generate(nums: list[int]) -> set[list[int]]:
        nums.sort()
        result = []

        def backtrack(start, path):
            result.append(path[:])
            for i in range(start, len(nums)):
                # if i > start and nums[i] == nums[i - 1]:
                #     continue  # skip duplicate sibling at this depth
                path.append(nums[i])
                backtrack(i + 1, path)
                path.pop()

        backtrack(0, [])
        return result
    
    
    @staticmethod
    def run_tests():
        actual, expected = PowerSubsets.generate([1, 2, 2]), [[], [1], [1, 2], [1, 2, 2], [2], [2, 2]]
        assert actual == expected
        
        print("PowerSubsets.run_tests() - SUCCESS")
                
class MinCoins:
    
    @staticmethod
    def generate_orig(coins: list[int], total: int) -> int:
        
        dp: list[int] = [0]
        for x in range(1, total+1):
            dp.append(sys.maxsize)
            for coin in coins:
                if coin <= x:
                    dp[x] = min(dp[x], dp[x - coin] + 1)
        
        return dp[-1] if dp[-1] < sys.maxsize else -1


    @staticmethod
    def generate(coins: list[int], total: int) -> int:
        
        dp = [0]
        for i in range(1, total+1):
            dp.append(float('inf'))
            for c in coins:
                if c <= i:
                    dp[i] = min(dp[i], dp[i - c] + 1)
                    
        return dp[-1] if dp[-1] < float('inf') else -1
    

    @staticmethod
    def run_tests():
        actual, expected = MinCoins.generate(deque([1, 3, 4]), 6), 2
        assert actual == expected, f"generate([1, 3, 4], 6) = {actual}, expected {expected}"
        actual, expected = MinCoins.generate(deque([2, 3]), 4), 2
        assert actual == expected, f"generate([5, 10, 25], 36) = {actual}, expected {expected}"

        actual, expected = MinCoins.generate(deque([1, 5, 10, 25]), 35), 2
        assert actual == expected, f"generate([1, 5, 10, 25], 35) = {actual}, expected {expected}"
        actual, expected = MinCoins.generate(deque([1, 5, 10, 25]), 68), 7
        assert actual == expected, f"generate([1, 5, 10, 25], 68) = {actual}, expected {expected}"
        actual, expected = MinCoins.generate(deque([5, 10, 25]), 36), -1
        assert actual == expected, f"generate([5, 10, 25], 36) = {actual}, expected {expected}"
        
        print("MinCoins.run_tests() - SUCCESS")
        
class Sorting[V]:
    
    @staticmethod
    def merge_sort(input: list[V], key: Callable[[V], any] = None) -> list[V]:
        
        if len(input) <= 1:
            return input
        
        mid = len(input) // 2
        left = Sorting.merge_sort(input[:mid], key=key)
        right = Sorting.merge_sort(input[mid:], key=key)

        i = j = k = 0
        result = []
        def _val(val: V) -> any:
                return val if key is None else key(val)
             
        while i < len(left) and j < len(right):
            if _val(left[i]) < _val(right[j]):
                result.append(left[i])
                i += 1
            else:
                result.append(right[j])
                j += 1
        
        while i < len(left):
            result.append(left[i])
            i += 1
        while j < len(right):
            result.append(right[j])
            j += 1
            
        return result

    @staticmethod
    def run_tests():
        input = [5, 2, 4, 1, 6, 3]
        sorted_input = [1, 2, 3, 4, 5, 6]
        actual, expected = Sorting[int].merge_sort(input), sorted_input
        assert actual == expected, f"merge_sort({input}) = {actual}, expected {expected}"
        
        @dataclass
        class _Peep:
            name: str
            age: int
        
        peeps: list[_Peep] = [
            _Peep("Bucky", 58),
            _Peep("Goldy", 48),
            _Peep("Hercules", 74),
            _Peep("Chief", 62),
            _Peep("Knute", 78),
            _Peep("Biff", 27),
        ]
        sorted_peeps: list[_Peep] = [
            _Peep("Biff", 27),            
            _Peep("Goldy", 48),
            _Peep("Bucky", 58),
            _Peep("Chief", 62),
            _Peep("Hercules", 74),
            _Peep("Knute", 78),
        ]
        actual, expected = Sorting[_Peep].merge_sort(peeps, key=lambda p: p.age), sorted_peeps
        assert actual == expected, f"merge_sort(peeps) = {actual}"
        
        print("Sorting.run_tests() - SUCCESS")

class CycleDetector:
    
    @staticmethod
    def verify(prereqs: list[list[int]]) -> bool:
        """Verifies that no cycles exist in the course syllabus.

        Returns:
            bool: True if no cycle is present, False otherwise
        """


        if prereqs is None or len(prereqs) <= 1:
            return True
        
        courses = set()
        pdict: dict[int,list[int]] = defaultdict(list)
        pdeps: dict[int,int] = defaultdict(int)
        for p in prereqs:
            courses.add(p[0])
            courses.add(p[1])
            pdict[p[1]].append(p[0])
            pdeps[p[0]] = pdeps[p[0]] + 1
            
        # print(f"verify() - courses: {courses} | pdict: {pdict} | pdeps: {pdeps}")
            
        q = [c for c in courses if c not in pdeps]
        order = []
        while len(q):
            c = q.pop()
            order.append(c)
            for d in pdict[c]:
                pdeps[d] = pdeps[d] - 1
                if pdeps[d] == 0:
                    q.append(d)
                    pdeps.pop(d)
        
        print(f"verify() - pdeps: {pdeps} | course order: {order}")
        return len(pdeps) == 0
                    
    @staticmethod
    def run_tests():
        actual, expected = CycleDetector.verify([[1,2], [1,3], [2,4], [3,4], [2,5]]), True
        assert actual == expected, f"CycleDetector.verify() = {actual}, expected {expected}"
        actual, expected = CycleDetector.verify([[1,2], [1,3], [2,4], [3,4], [2,5], [5,1]]), False
        assert actual == expected, f"CycleDetector.verify() = {actual}, expected {expected}"
        actual, expected = CycleDetector.verify([[1,2], [1,4], [3,4]]), True
        assert actual == expected, f"CycleDetector.verify() = {actual}, expected {expected}"

        print("CycleDetector.run_tests() - SUCCESS")

class LongestSubstring:
    
    @staticmethod
    def evaluate_slowly(data: str) -> int:
        streak: dict[str, int] = {}
        result = 0
        
        for i, c in enumerate(data):
            if c not in streak:
                streak[c] = i
                result = max(result, len(streak))
                # print(f"evaluate() - adding - i: {i}  c: {c}  max: {result}")
            else:
                irepeat = streak[c]
                for idrop in range(i - len(streak), irepeat+1):
                    # print(f"evaluate() - dropping - i: {i}  c: {c}  idrop: {idrop}")
                    streak.pop(data[idrop])
                streak[c] = i
                # print(f"evaluate() - dropped - i: {i}  streak: {streak}")
        
        return result

    @staticmethod
    def evaluate(data: str) -> int:
        last_seen = {}
        start = 0
        result = 0
        
        for i, c in enumerate(data):
            if c in last_seen:
                start = max(start, last_seen[c] + 1)
            last_seen[c] = i
            result = max(result, i - start + 1)

        return result
    
    @staticmethod
    def test_longestSubstring(input: str, expected: int):
        actual = LongestSubstring.evaluate(input)
        assert actual == expected, f"s.evaluate({input}) = {actual}, expected {expected}"
        
    @staticmethod
    def run_tests():
        LongestSubstring.test_longestSubstring("abcabcbb", 3)
        LongestSubstring.test_longestSubstring("abcdabcbb", 4)
        LongestSubstring.test_longestSubstring("abcabcdbb", 4)
        LongestSubstring.test_longestSubstring("bbbbb", 1)
        LongestSubstring.test_longestSubstring("pwwkew", 3)
        LongestSubstring.test_longestSubstring("pwwke", 3)
        LongestSubstring.test_longestSubstring("dvdf", 3)
        
        print("s.run_tests() - SUCCESS")


class BuySell:
    pass


class MergeSpans:
    
    @staticmethod
    def merge(spans: list[list[int]]) -> list[list[int]]:
        
        result = []
        cur = None
        for span in sorted(spans, key=lambda s: s[1]):
            if cur is None:
                cur = span
                continue
            
            if span[0] <= cur[1]:
                cur[1] = span[1]
                while len(result) > 0 and span[0] <= result[-1][1]:
                    combine = result.pop()
                    cur = [min(combine[0], span[0]), span[1]]

            else:
                result.append(cur)
                cur = span
                
        result.append(cur)
                
        return result
    
    
    @staticmethod
    def test_merge(spans: list[list[int]], expected: list[list[int]]):
        actual = MergeSpans.merge(spans)
        assert actual == expected, f"merge({spans}) = {actual}, expected {expected}"
    
    @staticmethod
    def run_tests():
        MergeSpans.test_merge([[8,10],[2,6],[1,3],[15,18],[10,11]], [[1,6],[8,11],[15,18]])
        MergeSpans.test_merge([[1,3],[2,7],[8,9],[4,11],[15,18]], [[1,11],[15,18]])
        
        print("MergeSpans.run_tests() - SUCCESS")


class GenerateParens:
    
    @staticmethod
    def execute(num: int) -> list[str]:
        
        def _perm(l: int, r: int, prefix: str):
            
            if l == 0 and r == 0:
                result.append(prefix)
                return
                
            if l > 0:
                _perm(l-1, r, prefix + "(")
            if r > l and r > 0:
                _perm(l, r-1, prefix + ")")

        result = []
        _perm(num, num, "")
        return result


    @staticmethod
    def test_parens(input: int, expected: list[str]):
        actual = GenerateParens.execute(input)
        print(f"generateParenthesis({input}) = {actual}")
        assert actual == expected, f"Expected generateParenthesis({input}) to equal {expected}, got {actual}"


    @staticmethod
    def run_tests():
        GenerateParens.test_parens(2, ["(())", "()()"])
        GenerateParens.test_parens(3, ["((()))", "(()())", "(())()", "()(())", "()()()"])

class AsyncFanOutIn:
    
    _DATE_FMT = '%Y-%m-%d_%H:%M:%S.%f%z'
    # _DATE_FMT = '%c'
    _NUM_TASKS = 3
    _TASK_LIFETIME = 5
    
    def ftime(self) -> str:
        return datetime.now().strftime(self._DATE_FMT)
    
    async def worker(self, id: int, count: int):        
        for i in range(count):
            print(f"worker {id}: {self.ftime()}")
            await asyncio.sleep(1)

    async def async_workers(self):
        print("async_workers() - STARTING")
        async with asyncio.TaskGroup() as tg:
            for i in range(self._NUM_TASKS):
                tg.create_task(self.worker(i+1, self._TASK_LIFETIME))
            
            await self.worker(58, 2)
        await self.worker(64, 2)
        
        print("async_workers() - COMPLETE")
        
    @staticmethod
    def run_tests():
        asyncio.run(AsyncFanOutIn().async_workers())

class IslandCounter:
    
    @staticmethod
    def count_bfs(input: list[list[int]]) -> int:
        
        N = len(input)
        # validate NxN, N>0
        _DIRS = [[-1, 0], [0, 1], [1, 0], [0, -1]]
        visited = [[False for _ in range(N)] for _ in range(N)]
        
        def _bfs(r: int, c: int):
            q = deque()
            q.append([r, c])
            
            while len(q):
                cur = q.pop()
                print(f"_bfs({newpt})")
                visited[newpt[0]][newpt[1]] = True

                for dir in _DIRS:
                    newpt = [cur[0] + dir[0], cur[1] + dir[1]]
                    if (
                        newpt[0] < 0 or newpt[0] >= N or newpt[1] < 0 or newpt[1] >= N 
                        or input[newpt[0]][newpt[1]] == 0 
                        or visited[newpt[0]][newpt[1]]
                    ):
                        continue
                    q.append(newpt)
            
        result = 0
        for r in range(N):
            for c in range(N):
                if input[r][c] == 1 and not visited[r][c]:
                    print(f"new island: [{r},{c}]")
                    result += 1
                    _bfs(r, c)
                    
        return result

    @staticmethod
    def run_tests():
        input1 = [
            [0, 1, 1, 0, 1],
            [1, 1, 1, 0, 0],
            [0, 0, 0, 0, 0],
            [1, 1, 0, 1, 1],
            [0, 1, 0, 0, 0],
        ]
        actual, expected = IslandCounter.count_bfs(input1), 4
        assert actual == expected, f"count_bfs(input1) = {actual}, expected {expected}"
        
        print("IslandCounter.run_tests() - SUCCESS")


class LongestSubsequence:
    
    @staticmethod
    def find_increasing_continuous(seq: list) -> int:
        dp = [1]
        cur = 1
        
        for i in range(1, len(seq)):
            
            if seq[i] > seq[i-1]:
               cur += 1
               dp.append(max(dp[i-1], cur))
            else:
                cur = 1
                dp.append(dp[-1])
                
        return dp[-1]
    
    @staticmethod
    def run_tests():
        input = [0, 1, 2, 1, 2, 3, 4, 1]
        actual, expected = LongestSubsequence.find_increasing_continuous(input), 4
        assert actual == expected, f"find_increasing_continuous({input}) = {actual}, expected {expected}"
        
        print("LongestSubsequence.run_tests() - SUCCESS")
        
class ClimbingStairs:
    
    @staticmethod
    def num_ways(num_steps: int) -> int:
        
        memo: dict[int,int] = {}
        
        def _climb(n: int):
            if n == 1:
                return 1
            if n == 2:
                return 2

            if n in memo: return memo[n]
            result = _climb(n-1) + _climb(n-2)
            memo[n] = result
            return result
    
        return _climb(num_steps)
    
    @staticmethod
    def paths(num_steps: int) -> list[list[int]]:
        
        if num_steps < 1:
            return []
        
        memo: dict[int,list[int]] = {2: [[1, 1], [2]], 1: [[1]]}
        
        def _climb(n: int) -> list[list[int]]:
            
            if n in memo: return memo[n]
            elif n == 1:
                return [[1]]
            elif n == 2:
                return [[1, 1], [2]]
            
            result = [[1] + suff for suff in _climb(n-1)] + \
                     [[2] + suff for suff in _climb(n-2)]
            memo[n] = result
            return result
    
        return _climb(num_steps)
    
    
    @staticmethod
    def run_tests():
        actual, expected = ClimbingStairs.num_ways(4), 5
        assert actual == expected, f"ClimbingStairs.num_ways(4) = {actual}, expected {expected}"
        actual, expected = ClimbingStairs.num_ways(5), 8
        assert actual == expected, f"ClimbingStairs.num_ways(5) = {actual}, expected {expected}"

        actual = ClimbingStairs.paths(4)
        expected = [[1, 1, 1, 1], [1, 1, 2], [1, 2, 1], [2, 1, 1], [2, 2]]
        assert actual == expected, f"ClimbingStairs.paths(4) = {actual}, expected {expected}"
        
        print("ClimbingStairs.run_tests() - SUCCESS")


def main():
    # LruCache.run_tests()
    # LruCacheOrderedDict.run_tests()
    # ConsistentHash.run_consistent_hash_tests()
    # BinaryTree.run_tests()
    # HashTable.run_tests()
    # DLinkedList.run_tests()
    
    # test_core_structures()
    
    # LfuCache.run_tests()
    # asyncio.run(TokenBucketLimiter.run_tests())
    # MergeSortedLists.run_tests()
    # PowerSubsets.run_tests()
    # MinCoins.run_tests()
    # Sorting.run_tests()
    # CycleDetector.run_tests()
    # LongestSubstring.run_tests()
    # MergeSpans.run_tests()
    # GenerateParens.run_tests()
    # AsyncFanOutIn.run_tests()
    # IslandCounter.run_tests()
    # LongestSubsequence.run_tests()
    # ConsistentHash2.run_tests()
    ClimbingStairs.run_tests()

if __name__ == "__main__":
    main()