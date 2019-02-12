package net.pgoldenb;

import com.google.common.collect.Lists;
import org.junit.Test;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import static junit.framework.TestCase.assertEquals;


public class LRUCacheTest {

    @Test
    public void test1() {

        LRUCacheGeneric<Integer,Integer> cache = new LRUCacheGeneric<>(3, -1);
        assertEquals(Integer.valueOf(-1), cache.get(12));

        cache.put(1, 11);
        cache.put(2, 22);
        cache.put(3, 33);

        assertEquals(
                Lists.newArrayList(3, 2, 1),
                cache.recencyList().stream().map(r -> r.key).collect(Collectors.toList())
        );

        assertEquals(Integer.valueOf(22), cache.get(2));
        assertEquals(
                Lists.newArrayList(2, 3, 1),
                cache.recencyList().stream().map(r -> r.key).collect(Collectors.toList())
        );

        cache.put(1, 111);
        assertEquals(
                Lists.newArrayList(1, 2, 3),
                cache.recencyList().stream().map(r -> r.key).collect(Collectors.toList())
        );
        assertEquals(Integer.valueOf(111), cache.get(1));

        cache.put(4, 44);
        cache.put(5, 55);
        assertEquals(Integer.valueOf(-1), cache.get(2));
        assertEquals(
                Lists.newArrayList(5, 4, 1),
                cache.recencyList().stream().map(r -> r.key).collect(Collectors.toList())
        );

    }

    class LRUCache {

        LRUCacheGeneric<Integer,Integer> cache;

        public LRUCache(int capacity) {
            cache = new LRUCacheGeneric<>(capacity, -1);
        }

        public int get(int key) {
            return cache.get(key);
        }

        public void put(int key, int value) {
            cache.put(key, value);
        }
    }

    class LRUCacheGeneric<K,V> {

        private Map<K,ValueBundle> cache;
        private V defaultVal;
        private RecencyList recencyList;

        public LRUCacheGeneric(int capacity, V defaultVal) {
            this.cache = new HashMap<K,ValueBundle>(capacity);
            this.defaultVal = defaultVal;
            this.recencyList = new RecencyList(capacity);
        }

        private class ValueBundle {
            public V value;
            public Recency recency;

            public ValueBundle(K key, V value) {
                this.value = value;
                this.recency = new Recency(key);
            }
        }

        public V get(K key) {

            if (!cache.containsKey(key))
                return defaultVal;

            ValueBundle b = cache.get(key);
            recencyList.toHead(b.recency);

            return b.value;
        }

        public void put(K key, V value) {

            if (cache.containsKey(key)) {
                ValueBundle b = cache.get(key);
                b.value = value;
                recencyList.toHead(b.recency);
                return;
            }

            ValueBundle b = new ValueBundle(key, value);
            Recency toDelete = recencyList.add(b.recency);
            if (toDelete != null)
                cache.remove(toDelete.key);
            cache.put(key, b);
        }

        public List<Recency> recencyList() {
            return recencyList.asList();
        }
    }

    private class Recency<K> {

        public Recency prev;
        public Recency next;
        public K key;

        public Recency(K key) {
            this.key = key;
        }
    }

    private class RecencyList<K> {

        private int size;
        private int capacity;
        private Recency<K> head;
        private Recency<K> tail;

        public RecencyList(int capacity) {
            this.size = 0;
            this.capacity = capacity;
            this.head = null;
            this.tail = null;
        }

        public void toHead(Recency newHead) {

            if (newHead == head)
                return;

            if (newHead == tail)
                tail = newHead.prev;

            newHead.prev.next = newHead.next;
            if (newHead.next != null)
                newHead.next.prev = newHead.prev;

            newHead.prev = null;
            newHead.next = head;
            head.prev = newHead;

            head = newHead;
        }

        public Recency add(Recency newHead) {

            if (head == null) {
                head = newHead;
                tail = newHead;
                size += 1;
                return null;
            }

            head.prev = newHead;
            newHead.next = head;
            head = newHead;

            if (size < capacity) {
                size += 1;
                return null;
            } else {
                Recency oldTail = tail;
                tail = tail.prev;
                oldTail.prev = null;
                tail.next = null;
                return oldTail;
            }
        }

        public List<Recency> asList() {
            List<Recency> l = new ArrayList<>(size);
            Recency r = head;
            while (r != null) {
                l.add(r);
                r = r.next;
            }
            return l;
        }
    }


/**
 * Your LRUCache object will be instantiated and called as such:
 * LRUCache obj = new LRUCache(capacity);
 * int param_1 = obj.get(key);
 * obj.put(key,value);
 */
}
