public abstract class Main {
    public static void main(String[] args) {
        int acc = 0;
        for (int i = 1; i <= 2; i++) {
            for (int j = i; j <= 2; j++) {
                acc += i + j;
            }
        }
        System.out.println(acc);
    }
}
