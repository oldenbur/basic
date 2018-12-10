package net.pgoldenb;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import org.junit.Test;

import java.io.FileNotFoundException;
import java.io.FileReader;
import java.io.Reader;
import java.util.ArrayList;
import java.util.List;

public class LinkedListTreeTest {

    @Test
    public void testLinkedListTree() throws FileNotFoundException {
        LLTNode tree = LLTNode.buildLLTree(new FileReader("llt_test1.json"));
        System.out.format("head: %s%n", tree);
    }


}

class LLTNode {

    private static final Gson gson = new GsonBuilder().setPrettyPrinting().create();

    private String data;
    private LLTCoord coord;

    private transient LLTNode prev;
    private LLTNode next;
    private LLTNode child;

    public static LLTNode buildLLTree(Reader r) {
        LLTNode root = gson.fromJson(r, LLTNode.class);

        root.coord = LLTCoord.rootValue();
        visitLLTree(root, (parent, prev, cur) -> {
            if (parent != null) {
                cur.coord = LLTCoord.childOf(parent.coord);
            } else if (prev != null) {
                cur.coord = LLTCoord.nextOf(prev.coord);
            }
            cur.prev = prev;
        });

        return root;
    }

    private LLTNode(String data, LLTNode next, LLTNode child) {
        this.data = data;
        this.next = next;
        this.child = child;
    }

    public String toString() {
        return gson.toJson(this);
    }

    interface LLTVisitor {
        void visit(LLTNode parent, LLTNode prev, LLTNode cur);
    }

    private static void visitLLTree(LLTNode root, LLTVisitor v) {

        if (root.next != null) {
            v.visit(null, root, root.next);
            visitLLTree(root.next, v);
        }
        if (root.child != null) {
            v.visit(root, null, root.child);
            visitLLTree(root.child, v);
        }
    }

    private static void printLLTPrevs(LLTNode n) {
        List<String> prevData = new ArrayList<>();
        LLTNode c = n;

        prevData.add(c.data);
        while (c.prev != null) {
            c = c.prev;
            prevData.add(c.data);
        }

        System.out.println(prevData);
    }

    static class LLTCoord {
        private List<Integer> coord;

        private LLTCoord(List<Integer> coord) {
            this.coord = coord;
        }

        public static LLTCoord rootValue() {
            LLTCoord c = new LLTCoord(new ArrayList<>());
            c.coord.add(1);
            return c;
        }

        public static LLTCoord childOf(LLTCoord c) {
            LLTCoord child = new LLTCoord(c.coord);
            child.coord.add(1);
            return child;
        }

        public static LLTCoord nextOf(LLTCoord c) {
            LLTCoord next = new LLTCoord(c.coord);
            int lastIndex = next.coord.size() - 1;
            next.coord.set(lastIndex, next.coord.get(lastIndex) + 1);
            return next;
        }

        public String toString() {
            String s = coord.get(0).toString();
            if (coord.size() > 1) {
                for (Integer i : coord.subList(1, coord.size())) {
                    s = s + "." + i.toString();
                }
            }
            return s;
        }
    }
}