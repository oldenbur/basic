package net.pgoldenb;

import org.junit.Test;

import java.util.*;

import static junit.framework.TestCase.assertEquals;
import static junit.framework.TestCase.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertTrue;

public class JScratchTest {

    @Test
    public void test1() {
        assertEquals(listOf(1, 2, 3), deleteDuplicates(listOf(1, 1, 1, 2, 2, 3, 3, 3)));
        assertEquals(listOf(1, 2, 3), deleteDuplicates(listOf(1, 2, 3)));
    }

    public ListNode deleteDuplicates(ListNode head) {

        if (head == null || head.next == null) return head;

        ListNode cur = head;
        while (cur.next != null) {
            if (cur.val == cur.next.val) {
                cur.next = cur.next.next;
            } else {
                cur = cur.next;
            }
        }

        return head;
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
        for (int i=1; i < vals.length; i++) {
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
