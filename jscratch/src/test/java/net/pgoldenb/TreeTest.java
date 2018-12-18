package net.pgoldenb;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import org.junit.Test;

import java.io.FileNotFoundException;
import java.io.FileReader;
import java.io.Reader;
import java.util.LinkedList;
import java.util.List;

import static org.junit.Assert.assertEquals;

public class TreeTest {

    @Test
    public void test1() throws FileNotFoundException {
        TreeNode<String> tree = TreeNode.buildTree(new FileReader("tree_test1.json"));
        System.out.format("head: %s%n", tree);
        assertEquals(6, TreeNode.maxHeight(tree, 0, 0));
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

    public static <T> int maxHeight(TreeNode<T> root, int curHeight, int maxHeight) {

        curHeight += 1;
        int newMax = curHeight;
        for (TreeNode<T> child : root.children) {
            int childHeight = maxHeight(child, curHeight, newMax);
            if (childHeight > newMax) newMax = childHeight;
         }

        return newMax;
    }

    public String toString() {
        return gson.toJson(this);
    }

}