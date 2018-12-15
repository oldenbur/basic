package net.pgoldenb;

import com.google.common.base.Stopwatch;
import com.google.common.base.Ticker;
import org.junit.Test;

import java.math.BigInteger;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.function.Consumer;

import static org.junit.Assert.assertEquals;

public class RingBufferTest {

    @Test
    public void test1() throws InterruptedException {
        RingBuffer<Integer> b = new RingBuffer<>(4);
        b.addToTail(1);
        b.addToTail(2);
        b.addToTail(3);
        b.addToTail(4);
        int r = b.removeFromHead();
        assertEquals(1, r);
        System.out.println(b.toString());
        assertEquals(1, 1);
    }

    public static final Duration DUR_ZERO = Duration.ZERO;
    public static final Duration DUR_SHORT = Duration.ofMillis(2000);

    private List<Duration> durList(Duration dur, int count) {
        List<Duration> durs = new ArrayList<>(count);
        for (int i=0; i < count; i++) durs.add(dur);
        return durs;
    }

    private Callable<Integer> createProducer(RingBuffer<Integer> buf, List<Duration> durList) {
        return () -> {
            scheduleConsumption(
                    durList,
                    i -> {
                        try {
                            Stopwatch watchAdd = Stopwatch.createStarted(Ticker.systemTicker());
                            buf.addToTail(i);
                            System.out.format("added %d: %s - took %s%n", i, buf, watchAdd);
                            System.out.flush();
                        } catch (InterruptedException e) {
                            e.printStackTrace();
                        }
                    });

            System.out.format("producer complete%n");
            System.out.flush();
            return null;
        };

    }

    private Callable<Integer> createConsumer(RingBuffer<Integer> buf, List<Duration> durList) {
        return () -> {
            scheduleConsumption(
                    durList,
                    i -> {
                        try {
                            Stopwatch watchRemove = Stopwatch.createStarted(Ticker.systemTicker());
                            int h = buf.removeFromHead();
                            System.out.format("removed %d: %s - took %s%n", h, buf, watchRemove);
                            System.out.flush();
                        } catch (InterruptedException e) {
                            e.printStackTrace();
                        }
                    });

            System.out.format("consumer complete%n");
            System.out.flush();
            return null;
        };

    }

    @Test
    public void test2() throws InterruptedException {

        ExecutorService exec= Executors.newCachedThreadPool();
        RingBuffer<Integer> buf = new RingBuffer<>(4);

        exec.invokeAll(Arrays.asList(
                createProducer(buf, durList(DUR_ZERO, 8)),
                createProducer(buf, durList(DUR_ZERO, 8)),
                createProducer(buf, durList(DUR_SHORT, 4)),
                createConsumer(buf, durList(DUR_ZERO, 20))
                ));
        exec.shutdown();
    }

    private void scheduleConsumption(List<Duration> durs, Consumer<Integer> consumer) throws InterruptedException {
        int i = 1;
        for (Duration dur : durs) {
            Thread.sleep(dur.toMillis());
            consumer.accept(i++);
        }
    }

    class RingBuffer<T> {
        private List<T> data;
        private int head;
        private int tail;
        private boolean isEmpty = true;

        public RingBuffer(int size) {
            this.data = new ArrayList<>(size);
            for (int i = 0; i < size; i++) data.add(null);
        }

        public synchronized void addToTail(T item) throws InterruptedException {
//            System.out.format("addToTail(%s) with %s stored: %d%n", item, this, stored());
//            System.out.flush();
            try {
                while (stored() >= data.size()){
//                    System.out.format("addToTail(%s) waiting%n", item, this);
//                    System.out.flush();
                    wait();
                }

                data.set(tail, item);
                isEmpty = false;
                tail = (tail + 1) % data.size();

            } finally {
                notify();
            }
        }

        public synchronized T removeFromHead() throws InterruptedException {
//            System.out.format("removeFromHead() with %s%n", this);
//            System.out.flush();
            try {
                while (isEmpty){
//                    System.out.format("removeFromHead() on %s waiting%n", this);
//                    System.out.flush();
                    wait();
                }

                T val = data.get(head);
                head = (head + 1) % data.size();
                isEmpty = (head == tail);
                return val;

            } finally {
                notify();
            }
        }

        public synchronized int stored() {
            int stored = 0;
            if (!isEmpty) {
                if (tail != head) {
                    stored = BigInteger.valueOf(tail - head).mod(BigInteger.valueOf(data.size())).intValue();
                } else {
                    stored = data.size();
                }
            }
            return stored;
        }

        public synchronized String toString() {

            if (isEmpty) return "[]";

            StringBuilder s = new StringBuilder("[");
            s.append(data.get(head));
            int i = (head + 1) % data.size();
            while (i != tail) {
                s.append(", ").append(data.get(i));
                i = (i + 1) % data.size();
            }
            return s.append("]").toString();

//            return String.format("head: %d  tail: %d  stored: %d  data.size: %d  data: %s  buf: %s%n",
//                    head, tail, stored(), data.size(), data, s);
        }
    }
}

