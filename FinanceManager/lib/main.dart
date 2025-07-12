import 'package:financemanager/firebase_options.dart';
import 'package:financemanager/screens/signup.dart';
import 'package:financemanager/screens/login.dart';
import 'package:financemanager/screens/dashboard.dart';
import 'package:financemanager/screens/add_income.dart';
import 'package:financemanager/screens/expense_entry.dart';
import 'package:financemanager/screens/SavedSavingPlanScreen.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );
  runApp(MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,  // Remove debug banner
      title: 'Finance Manager',
      theme: ThemeData(
        primarySwatch: Colors.deepPurple,
        scaffoldBackgroundColor: Colors.grey[100],
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.deepPurple,
            foregroundColor: Colors.white,
            padding: EdgeInsets.symmetric(vertical: 15, horizontal: 25),
            textStyle: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
          ),
        ),
      ),
      initialRoute: '/signup',
      routes: {
        '/signup': (context) => Signup(),
        '/login': (context) => Login(),
        '/dashboard': (context) => DashboardScreen(),
        '/add_income': (context) => AddIncomeScreen(),
        '/add_expense': (context) => AddExpenseScreen(),
        '/saved_savings_plans': (context) => SavedSavingsPlansScreen(),

      },
    );
  }
}
