
from collections import OrderedDict
from dataclasses import dataclass, field
import sys
from typing import Callable
import bisect

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


def main():
    # LruCache.run_tests()
    # LruCacheOrderedDict.run_tests()
    ConsistentHash.run_consistent_hash_tests()

if __name__ == "__main__":
    main()