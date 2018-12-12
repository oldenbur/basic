package net.pgoldenb;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import org.junit.Test;

public class JScratchTest {

    @Test
    public void test1() {
        Node root = new Node(6);
        root = insert(root, 4);
        root = insert(root, 12);
        root = insert(root, 8);
        root = insert(root, 9);
        System.out.println(root.toString());
    }

    static class Node {
        int val;       //Value
        int ht;        //Height
        Node left;     //Left child
        Node right;    //Right child

        private static final Gson gson = new GsonBuilder().setPrettyPrinting().create();

        public Node(int val) { this.val = val; }

        public String toString() { return gson.toJson(this); }
    }

    static enum Path{LEFT, RIGHT};

    static Node insert(Node root, int val) {
        System.out.format("insert(%d, %d)%n", root.val, val);
        if (val <= root.val) {
            if (root.left != null) {
                insert(root.left, val);
                int lht = root.left.ht + 1;
                if (lht > root.ht) {
                    root.ht = lht;
                    root = balance(root);
                }
            } else {
                root.left = new Node(val);
                if (root.ht < 1) root.ht = 1;
            }
        } else {
            if (root.right != null) {
                insert(root.right, val);
                int rht = root.right.ht + 1;
                if (rht > root.ht) {
                    root.ht = rht;
                    root = balance(root);
                }
            } else {
                root.right = new Node(val);
                if (root.ht < 1) root.ht = 1;
            }
        }
        return root;
    }

    static Node balance(Node root) {
        int bf = calcBf(root);
        System.out.format("Node: %d  bf: %d%n", root.val, bf);

        if (bf < -1) {
        } else if (bf > 1) {
            if (calcBf(root.right) > 1) {
                System.out.println("Right-Left on " + root.toString());
                Node piv = root.right;
                root.right = piv.left;
                root.right.ht -= 1;
                piv.left = root.right.right;
                root.right.right.ht += 1;
                root.right.right = piv;
            }
            System.out.println("Right-Right on " + root.toString());
            Node piv = root.right;
            root.right = root.right.right;
            piv.right = piv.left;
            piv.left = root.left;
            root.left = piv;
            root.left.ht -= 1;
            int tmp = piv.val;
            piv.val = root.val;
            root.val = tmp;
            root.ht -= 1;
        }
        return root;
    }

    static int calcBf(Node n) {
        int bf = 0;
        if (n.left != null) bf -= n.left.ht;
        if (n.right != null) bf += n.right.ht;
        return bf;
    }
}

