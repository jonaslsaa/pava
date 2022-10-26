public class Main {
    public static void main(String[] args) {
        int a = 3;
        int b = 4;
        System.out.println(Test.add(a, b));
    }
}

class Test {
    public static int add(int a, int b) {
        return a + b;
    }
}