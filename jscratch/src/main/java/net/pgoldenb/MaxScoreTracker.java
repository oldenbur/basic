package net.pgoldenb;
import java.io.BufferedWriter;
import java.io.FileWriter;
import java.util.Random;
import java.util.Scanner;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReadWriteLock;
import java.util.concurrent.locks.ReentrantReadWriteLock;

/**
 * A tracker of the maximum score that has been seen so far.
 */
public class MaxScoreTracker {

    private int maxScore = Integer.MIN_VALUE;
    private final ReadWriteLock rwl = new ReentrantReadWriteLock();
    private final Lock r = rwl.readLock();
    private final Lock w = rwl.writeLock();

    /**
     * Get the current value of the maximum score.
     */
    public int getMaxScore() {
        r.lock();
        try {
            return maxScore;
        } finally { r.unlock(); }
    }

    /**
     * Update the maximum score if, and only if, the given score is greater than
     * the current maximum score.
     */
    public void updateMaxScoreIfNecessary(int score) {
        if (score > maxScore) {
            maxScore = score;
        }
     }
    private static final Scanner scanner = new Scanner(System.in);

    public static void main(String[] args) throws Exception {
        BufferedWriter bufferedWriter = new BufferedWriter(new FileWriter(System.getenv("OUTPUT_PATH")));

        int numThreads = scanner.nextInt();
        scanner.skip("(\r\n|[\n\r\u2028\u2029\u0085])?");

        int iters = scanner.nextInt();
        scanner.skip("(\r\n|[\n\r\u2028\u2029\u0085])?");

        int res = test(numThreads, iters);

        bufferedWriter.write(String.valueOf(res));
        bufferedWriter.newLine();

        bufferedWriter.close();

        scanner.close();
    }

    private static int test(int numThreads, int iters) throws Exception {
        Random random = new Random();
        int maxDelta = 0;
        for (int iter = 0; iter < iters; ++iter) {
            MaxScoreTracker maxScoreTracker = new MaxScoreTracker();
            Thread[] threads = new Thread[numThreads];
            int maxScore = Integer.MIN_VALUE;
            CountDownLatch startSignal = new CountDownLatch(1);
            for (int i = 0; i < numThreads; ++i) {
                final int score = random.nextInt();
                maxScore = Math.max(maxScore, score);
                threads[i] = new Thread(() -> {
                    try {
                        startSignal.await();
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                    }
                    maxScoreTracker.updateMaxScoreIfNecessary(score);
                });
                threads[i].start();
            }
            startSignal.countDown();
            for (Thread thread : threads) {
                thread.join();
            }
            maxDelta = Math.max(maxDelta, Math.abs(maxScoreTracker.getMaxScore() - maxScore));
        }
        return maxDelta;
    }
}

