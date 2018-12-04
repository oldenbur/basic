package net.pgoldenb;

import com.google.common.base.Stopwatch;
import com.google.common.base.Ticker;

import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.Consumer;

public class ConcurrentListsTest {

    private static final int numVisitors = 100;
    private static final int numApenders = 1000;
    private static final int listSize = 100000;

    private final static CountDownLatch visitors = new CountDownLatch(numVisitors);

    public static void main(String[] args) throws InterruptedException, ExecutionException {

        String prefix = "cowa";
        Stopwatch watchInit = Stopwatch.createStarted(Ticker.systemTicker());
//        final List<String> tList = new CopyOnWriteArrayList<String>(buildTestData(prefix, listSize));
        final List<String> tList = Collections.synchronizedList(buildTestData(prefix, listSize));
        System.out.format("elapsed init: %s%n", watchInit);

        Set<Callable<Integer>> tasks = new HashSet<>();
        for (int i = 0; i < numVisitors; i++) {
            tasks.add(() -> visitListItems(s -> {}, Duration.ZERO, tList));
        }
        for (int i = 0; i < numApenders; i++) {
            tasks.add(() -> appendListItems(prefix, Duration.ZERO, tList));
        }

        Stopwatch watch = Stopwatch.createStarted(Ticker.systemTicker());
        ExecutorService exec = Executors.newFixedThreadPool(tasks.size());
        List<Future<Integer>> futures = exec.invokeAll(tasks);

        for (Future<Integer> f : futures) {
//            System.out.format("future complete: %d%n", f.get());
        }
        exec.shutdown();
        System.out.format("elapsed sl: %s%n", watch);
    }

    private static List<String> buildTestData(String prefix, int size) {
        List<String> data = new ArrayList<>(size);
        for (int i = 1; i <= size; i++) {
            data.add(String.format("%s%d", prefix, i));
        }
        return data;
    }

    private static int appendListItems(String prefix, Duration delay, List<String> tList) {

        int i = 1;
        try {
            while (true) {
                tList.add(String.format("%s%d", prefix, i++));
                if (!delay.isZero()) {
                    Thread.sleep(delay.toMillis());
                } else {
                    long runningVisitors = visitors.getCount();
//                    System.out.format("appendListItems %d running visitors%n", runningVisitors);
                    if (runningVisitors <= 0) {
//                        System.out.println("appendListItems returning");
                        return i;
                    }
                }
            }
        } catch (InterruptedException e) {
            System.out.println("appendListItems caught interruption");
        }
        return i;
    }

    private static <T> int visitListItems(Consumer<T> c, Duration delay, List<T> tList) throws InterruptedException {
        try {
            for (T t : tList) {
                c.accept(t);
                sleepOrThrow(delay);
            }
            return tList.size();
        } finally {
            visitors.countDown();
//            System.out.println("released");
        }
    }

    private static void sleepOrThrow(Duration delay) {
        if (delay.isZero()) {
            return;
        }

        try {
            Thread.sleep(delay.toMillis());
        } catch (InterruptedException e) {
            throw new RuntimeException(e);
        }
    }
}