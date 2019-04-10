package net.pgoldenb;

import org.junit.Test;

import java.util.Arrays;
import java.util.List;

import static org.junit.Assert.assertTrue;

public class QuickSortTest {

    @Test
    public void test1() {

        assertTrue(isSorted(quickSort(l(1, 2, 3, 4))));
        assertTrue(isSorted(quickSort(l(4, 3, 2, 1))));
        assertTrue(isSorted(quickSort(l(5, 3, 8, 1, 2, 9, 4, 0, 7, 6))));
    }

    <T extends Comparable<T>> boolean isSorted(List<T> data) {
        if (data == null || data.size() < 2) return true;

        for (int i = 1; i < data.size(); i++) {
            if (data.get(i - 1).compareTo(data.get(i)) > 0)
                return false;
        }
        return true;
    }

    public <T extends Comparable<T>> List<T> quickSort(List<T> data) {
        if (data == null || data.size() < 2) return data;
        quickSort(data, 0, data.size() - 1);
        return data;
    }

    <T extends Comparable<T>> void quickSort(List<T> data, int lo, int hi) {
        if (lo >= hi) return;
        int p = partition(data, lo, hi);
        quickSort(data, lo, p);
        quickSort(data, p + 1, hi);
    }

    <T extends Comparable<T>> int partition(List<T> data, int lo, int hi) {
        T pVal = data.get((lo + hi) / 2);
        int i = lo - 1, j = hi + 1;
        while (true) {

            do { i += 1; } while (data.get(i).compareTo(pVal) < 0);
            do { j -= 1; } while (data.get(j).compareTo(pVal) > 0);

            if ( i >= j) return j;
            swap(data, i, j);
        }
    }

    <T> void swap(List<T> data, int i, int j) {
        if (data == null || i < 0 || i >= data.size() || j < 0 || j >= data.size())
            throw new IllegalStateException(String.format("bad parameters to swap - i: %d  j: %d  data.size: %s", i, j, (data == null ? "null" : String.valueOf(data.size()))));
        if (i == j) return;

        T tmp = data.get(i);
        data.set(i, data.get(j));
        data.set(j, tmp);
    }


    /* * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * */

    static int[] ints(int... vals) { return vals; }

    static boolean intsEqual(int[] a, int[] b) {
        if (a == null && b == null) return true;
        if (a == null || b == null || a.length != b.length) return false;
        for (int i = 0; i < a.length; i++) {
            if (a[i] != b[i]) return false;
        }
        return true;
    }

    static boolean intintsEqual(int[][] a, int[][] b) {
        if (a == null && b == null) return true;
        if (a == null || b == null || a.length != b.length) return false;

        for (int i = 0; i < a.length; i++) {
            if (!intsEqual(a[i], b[i]))
                return false;
        }
        return true;
    }

    static <T> List<T> l(T... vals) { return Arrays.asList(vals); }

    static TreeNode treeOf(int val, TreeNode left, TreeNode right) {
        TreeNode ret = new TreeNode(val);
        ret.left = left;
        ret.right = right;
        return ret;
    }

    static TreeNode treeOf(int val) { return treeOf(val, null, null); }

    static TreeNode treeOf(int val, TreeNode left) { return treeOf(val, left, null); }

    static class TreeNode {
        int val;
        TreeNode left;
        TreeNode right;

        TreeNode(int x) { val = x; }

        @Override
        public boolean equals(Object other) {

            if (other == null) return false;
            if (!(other instanceof TreeNode)) return false;

            TreeNode otherNode = (TreeNode) other;

            if (val != otherNode.val) return false;
            if (left == null) {
                if (otherNode.left != null) return false;
            } else if (!left.equals(otherNode.left)) {
                return false;
            }

            if (right == null) {
                if (otherNode.right != null) return false;
            } else if (!right.equals(otherNode.right)) {
                return false;
            }

            return true;
        }
    }

    static ListNode listOf(int... vals) {
        if (vals == null || vals.length < 1) return null;

        ListNode head = new ListNode(vals[0]);
        ListNode cur = head;
        for (int i = 1; i < vals.length; i++) {
            cur.next = new ListNode(vals[i]);
            cur = cur.next;
        }
        return head;
    }

    static public class ListNode {
        int val;
        ListNode next;

        ListNode(int x) { val = x; }

        @Override
        public boolean equals(Object other) {

            if (other == null) return false;
            if (!(other instanceof ListNode)) return false;

            ListNode thisNode = this;
            ListNode otherNode = (ListNode) other;

            while (thisNode != null) {
                if (otherNode == null || thisNode.val != otherNode.val) return false;
                thisNode = thisNode.next;
                otherNode = otherNode.next;
            }

            return (otherNode == null);
        }
    }

}
