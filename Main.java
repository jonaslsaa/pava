public class Main {
    static int a = 1;
    public static void main(String[] args) {
        setA(2);
        System.out.println(a);
    }

    public static void setA(int b) {
        a += b;
    }
}
