package net.pgoldenb;

import org.junit.Test;

import java.util.*;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

public class HeapTest {

    @Test
    public void testParentOf() {
        assertEquals(0, ArrayHeapAsc.parentOf(0));
        assertEquals(0, ArrayHeapAsc.parentOf(1));
        assertEquals(0, ArrayHeapAsc.parentOf(2));
        assertEquals(1, ArrayHeapAsc.parentOf(3));
        assertEquals(1, ArrayHeapAsc.parentOf(4));
        assertEquals(2, ArrayHeapAsc.parentOf(5));
        assertEquals(2, ArrayHeapAsc.parentOf(6));
        assertEquals(3, ArrayHeapAsc.parentOf(7));
        assertEquals(3, ArrayHeapAsc.parentOf(8));
        assertEquals(4, ArrayHeapAsc.parentOf(9));
        assertEquals(4, ArrayHeapAsc.parentOf(10));
    }

    @Test
    public void testAddAndGetMin() {
        ArrayHeapAsc<Integer> heap = buildTestHeap();
        assertEquals((Integer)2, heap.peek());
    }

    @Test
    public void testPoll() {
        ArrayHeapAsc<Integer> heap = buildTestHeap();
        System.out.format("heap: %s%n", heap.toString());
        assertEquals((Integer)2, heap.poll());
        System.out.format("heap: %s%n", heap.toString());
        assertEquals((Integer)3, heap.peek());
    }

    @Test
    public void testIterator() {
        ArrayHeapAsc<Integer> heap = buildTestHeap();
        System.out.format("heap: %s%n", heap.toString());
        assertEquals((Integer)2, heap.poll());
        System.out.format("heap: %s%n", heap.toString());
        assertEquals((Integer)3, heap.peek());
    }

    private ArrayHeapAsc<Integer> buildTestHeap() {
        ArrayHeapAsc<Integer> heap = new ArrayHeapAsc<>();
        assertTrue(heap.add(5));
        assertTrue(heap.add(14));
        assertTrue(heap.add(8));
        assertTrue(heap.add(12));
        assertTrue(heap.add(2));
        assertTrue(heap.add(7));
        assertTrue(heap.add(3));
        assertTrue(heap.add(9));
        return heap;
    }
}

class ArrayHeapAsc<T extends Comparable<T>> implements Queue<T> {

    private List<T> data = new ArrayList<>();

    public static int childLeftOf(int i) { return 2*i + 1; }
    public static int childRightOf(int i) { return 2*i + 2; }
    public static int parentOf(int i) {

        if (i == 0) return 0;

        if (i % 2 == 0) i -=2;
        else i -= 1;

        return i/2;
    }

    private int bubbleUp(int i) {

        if (i < 0 || i >= data.size())
            throw new IllegalArgumentException(String.format("invalid bubbleUp argument %d must be in range [0, %d]", i, data.size()-1));
        else if (i == 0)
            return 0;

        T item = data.get(i);
        int ip = parentOf(i);
        T parent = data.get(ip);
        if (item.compareTo(parent) < 0) {
            data.set(i, parent);
            data.set(ip, item);
            return bubbleUp(ip);
        } else {
            return i;
        }
    }

    private int bubbleDown(int i) {

        if (i < 0 || i >= data.size())
            throw new IllegalArgumentException(String.format("invalid bubbleDown argument %d must be in range [0, %d]", i, data.size()-1));

        T item = data.get(i);
        T minChild;

        int imin = childLeftOf(i);
        if (imin >= data.size())
            return i;
        else
            minChild = data.get(imin);

        int ir = childRightOf(i);
        if (ir < data.size()) {
            T rChild = data.get(ir);
            if (rChild.compareTo(minChild) < 0) {
                imin = ir;
                minChild = rChild;
            }
        }

        if (item.compareTo(minChild) > 0) {
            data.set(i, minChild);
            data.set(imin, item);
            return bubbleDown(imin);
        } else {
            return i;
        }
    }

    @Override
    public int size() {
        return data.size();
    }

    @Override
    public boolean isEmpty() {
        return size() <= 0;
    }

    @Override
    public boolean contains(Object o) {
        throw new UnsupportedOperationException();
    }

    @Override
    public Iterator<T> iterator() {

        ArrayHeapAsc<T> copy = new ArrayHeapAsc<>();
        copy.data = new ArrayList<>(data);
        return new Iterator<T>() {

            @Override
            public boolean hasNext() {
                return copy.size() > 0;
            }

            @Override
            public T next() {
                return copy.poll();
            }
        };
    }

    @Override
    public Object[] toArray() {
        throw new UnsupportedOperationException();
    }

    @Override
    public <T1> T1[] toArray(T1[] a) {
        throw new UnsupportedOperationException();
    }

    @Override
    public boolean add(T t) {
        data.add(t);
        return (bubbleUp(data.size() - 1) >= 0);
    }

    @Override
    public boolean remove(Object o) {
        throw new UnsupportedOperationException();
    }

    @Override
    public boolean containsAll(Collection<?> c) {
        throw new UnsupportedOperationException();
    }

    @Override
    public boolean addAll(Collection<? extends T> c) {
        return false;
    }

    @Override
    public boolean removeAll(Collection<?> c) {
        throw new UnsupportedOperationException();
    }

    @Override
    public boolean retainAll(Collection<?> c) {
        throw new UnsupportedOperationException();
    }

    @Override
    public void clear() {
        data = new ArrayList<>();
    }

    @Override
    public boolean offer(T t) {
        return add(t);
    }

    @Override
    public T remove() {
        throw new UnsupportedOperationException();
    }

    @Override
    public T poll() {
        if (data.size() < 1)
            return null;

        T last = data.remove(data.size() - 1);
        T head = data.set(0, last);
        bubbleDown(0);
        return head;
    }

    @Override
    public T element() {
        T item = peek();
        if (item == null)
            throw new NoSuchElementException();
        else
            return item;
    }

    @Override
    public T peek() {
        if (data.size() > 0)
            return data.get(0);
        else
            return null;
    }

    @Override
    public String toString() {
        return data.toString();
    }
}
