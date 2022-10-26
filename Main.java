public class Main {
    public static void main(String[] args) {
        int a = 3;
        int b = 4;
        int acc = 0;
        for (int i = 0; i < 3; i++) {
            acc += i*a + i*b;
        }
        System.out.println(acc);
       // System.out.println(Test.add(a, b));
    }
}

class Test {
    public static int add(int a, int b) {
        return a + b;
    }
}