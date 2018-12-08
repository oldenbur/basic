package net.pgoldenb;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import org.junit.Test;

import java.io.FileNotFoundException;
import java.io.FileReader;

public class LinkedListTreeTest {

    @Test
    public void testLinkedListTree() throws FileNotFoundException {
        Gson gson = new Gson();
        LLTNode head = gson.fromJson(new FileReader("llt_test1.json"), LLTNode.class);
        System.out.format("head: %s%n", head);
    }


}

class LLTNode {

    private static final Gson gson = new GsonBuilder().setPrettyPrinting().create();

    private String data;
    private String tag;
    private String prevTag;

    private transient LLTNode prev;
    private LLTNode next;
    private LLTNode child;

    public LLTNode(String data, LLTNode next, LLTNode child) {
        this.data = data;
        this.prevTag = prevTag;
        this.prev = prev;
        this.next = next;
        this.child = child;
    }

    public String toString() {
        return gson.toJson(this);
    }

}