package net.pgoldenb;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import org.junit.Test;

import java.io.FileNotFoundException;
import java.io.FileReader;
import java.io.Reader;
import java.util.*;

import static org.junit.Assert.assertEquals;

public class TreeTest {

    @Test
    public void testMaxHeight() throws FileNotFoundException {
        TreeNode<String> tree = TreeNode.buildTree(new FileReader("tree_test1.json"));
//        System.out.format("head: %s%n", tree);
        assertEquals(6, TreeNode.maxHeight(tree));
    }

    @Test
    public void testPreorder() throws FileNotFoundException {
        TreeNode<String> tree = TreeNode.buildTree(new FileReader("tree_test2.json"));
        System.out.println("testPreorder:");
        TreeNode.preorder(tree);
    }

    @Test
    public void testPreorderIter() throws FileNotFoundException {
        TreeNode<String> tree = TreeNode.buildTree(new FileReader("tree_test2.json"));
        System.out.println("testPreorderIter:");
        TreeNode.preorderIter(tree);
    }

    @Test
    public void findAncestor() throws FileNotFoundException {
        TreeNode<String> tree = TreeNode.buildTree(new FileReader("tree_test3.json"));
        TreeNode<String> a = TreeNode.findNode(tree, "8");
        assertEquals(a, TreeNode.commonAncestor(tree, "14", "4"));
    }

}

class TreeNode<T> {

    private static final Gson gson = new GsonBuilder().setPrettyPrinting().create();

    private T data;
    private List<TreeNode<T>> children = new LinkedList<>();

    public static TreeNode buildTree(Reader r) {
        TreeNode<String> root = gson.fromJson(r, TreeNode.class);
        return root;
    }

    public static <T> int maxHeight(TreeNode<T> root) {

        int newMax = 1;
        for (TreeNode<T> child : root.children) {
            int childHeight = maxHeight(child) + 1;
            if (childHeight > newMax) newMax = childHeight;
         }

        return newMax;
    }

    public static <T> void preorder(TreeNode<T> root) {
        System.out.println(root.data);
        for (TreeNode<T> child : root.children) {
            preorder(child);
        }
    }

    public static <T> void preorderIter(TreeNode<T> root) {
        Deque<TreeNode<T>> deque = new LinkedList<TreeNode<T>>();
        deque.addFirst(root);
        while (!deque.isEmpty()) {
            TreeNode<T> cur = deque.removeFirst();
            System.out.println(cur.data);
            for (int i = cur.children.size() - 1; i >= 0; i--)
                deque.addFirst(cur.children.get(i));
        }
    }

    public static <T> TreeNode<T> findNode(TreeNode<T> root, T val) {

        if (root.data.equals(val)) return root;
        for (TreeNode<T> child : root.children) {
            TreeNode<T> n = findNode(child, val);
            if (n != null) return n;
        }
        return null;
    }

    public static <T> Map<TreeNode<T>,TreeNode<T>> parentMap(
            Map<TreeNode<T>,TreeNode<T>> parents,
            TreeNode<T> parent,
            TreeNode<T> cur
    ) {

        if (parents == null) parents = new HashMap<>();
        if (parent != null) parents.put(cur, parent);
        for (TreeNode<T> child : cur.children) parents = parentMap(parents, cur, child);

        return parents;
    }

    public static <T> TreeNode<T> commonAncestor(TreeNode<T> root, T val1, T val2) {

        TreeNode<T> n1 = findNode(root, val1);
        if (n1 == null) return null;

        TreeNode<T> n2 = findNode(root, val2);
        if (n2 == null) return null;

        Map<TreeNode<T>,TreeNode<T>> parents = parentMap(null, null, root);

        Set<TreeNode<T>> n1Parents = new HashSet<>();
        TreeNode<T> n1Parent = parents.get(n1);
        while (n1Parent != null) {
            n1Parents.add(n1Parent);
            n1Parent = parents.get(n1Parent);
        }

        TreeNode<T> n2Parent = parents.get(n2);
        while(n2Parent != null) {
            if (n1Parents.contains(n2Parent)) return n2Parent;
            n2Parent = parents.get(n2Parent);
        }

        return null;
    }

    public String toString() {
//        return gson.toJson(this);
        return data.toString();
    }

}