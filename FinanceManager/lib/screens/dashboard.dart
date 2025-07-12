import 'package:financemanager/screens/SavingPlanScreen.dart';
import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';

class DashboardScreen extends StatefulWidget {
  @override
  _DashboardScreenState createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  double totalIncome = 0;
  double spentAmount = 0;
  Map<String, double> categoryExpenses = {};
  String? userId;
  String currentMonth = "";
  User? user;

  @override
  void initState() {
    super.initState();
    user = FirebaseAuth.instance.currentUser;
    userId = user?.uid;
    currentMonth = getCurrentMonth();
    if (userId != null) {
      checkAndCreateNewMonth();
    }
  }

  String getCurrentMonth() {
    DateTime now = DateTime.now();
    return "${now.year}-${now.month.toString().padLeft(2, '0')}";
  }

  Future<void> checkAndCreateNewMonth() async {
    if (userId == null) return;

    DocumentSnapshot snapshot = await FirebaseFirestore.instance
        .collection('users')
        .doc(userId)
        .collection('records')
        .doc(currentMonth)
        .get();

    if (!snapshot.exists) {
      await FirebaseFirestore.instance
          .collection('users')
          .doc(userId)
          .collection('records')
          .doc(currentMonth)
          .set({
        'totalIncome': 0,
        'spentAmount': 0,
        'categoryExpenses': {},
      });
    }

    fetchUserData();
  }

  Future<void> fetchUserData() async {
    if (userId == null) return;

    DocumentSnapshot snapshot = await FirebaseFirestore.instance
        .collection('users')
        .doc(userId)
        .collection('records')
        .doc(currentMonth)
        .get();

    if (snapshot.exists) {
      setState(() {
        totalIncome = (snapshot['totalIncome'] ?? 0).toDouble();
        spentAmount = (snapshot['spentAmount'] ?? 0).toDouble();
        categoryExpenses = Map<String, double>.from(
            snapshot['categoryExpenses']?.map((key, value) => MapEntry(key, value.toDouble())) ?? {});
      });
    }
  }

  Future<void> updateIncome(double income) async {
    if (userId == null) return;
    setState(() {
      totalIncome = income;
    });

    await FirebaseFirestore.instance
        .collection('users')
        .doc(userId)
        .collection('records')
        .doc(currentMonth)
        .set({
      'totalIncome': totalIncome,
    }, SetOptions(merge: true));
  }

  Future<void> addExpense(String category, double amount) async {
    if (userId == null) return;

    setState(() {
      spentAmount += amount;
      categoryExpenses[category] = (categoryExpenses[category] ?? 0) + amount;
    });

    await FirebaseFirestore.instance
        .collection('users')
        .doc(userId)
        .collection('records')
        .doc(currentMonth)
        .set({
      'spentAmount': spentAmount,
      'categoryExpenses': categoryExpenses,
    }, SetOptions(merge: true));
  }

  Future<void> logout() async {
    await FirebaseAuth.instance.signOut();
    Navigator.pushReplacementNamed(context, '/login');
  }

  @override
  Widget build(BuildContext context) {
    double remainingBalance = totalIncome - spentAmount;

    return Scaffold(
      appBar: AppBar(
        title: Text("Finance Dashboard"),
        backgroundColor: Colors.teal,
      ),
      drawer: Drawer(
        backgroundColor: Colors.deepPurple[900],
        child: Column(
          children: [
            UserAccountsDrawerHeader(
              accountName: Text(user?.displayName ?? "User Name", style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              accountEmail: Text(user?.email ?? "user@example.com", style: TextStyle(fontSize: 14)),
              currentAccountPicture: CircleAvatar(
                backgroundColor: Colors.white,
                child: Icon(Icons.person, size: 40, color: Colors.deepPurple),
              ),
              decoration: BoxDecoration(color: Colors.deepPurple),
            ),
            ListTile(
              leading: Icon(Icons.logout, color: Colors.white),
              title: Text("Logout", style: TextStyle(color: Colors.white, fontSize: 18)),
              onTap: logout,
            ),
            SizedBox(height: 20),
            ListTile(
              leading: Icon(Icons.savings, color: Colors.white),
              title: Text("Savings Plan", style: TextStyle(color: Colors.white, fontSize: 18)),
              onTap: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (context) => SavingsPlanScreen()),
                );
              },
            ),
          ],
        ),
      ),
      body: Container(
        decoration: BoxDecoration(
          image: DecorationImage(
            image: AssetImage('images/wallpaper.jpg'),
            fit: BoxFit.cover,
            onError: (exception, stackTrace) {
              print("Image load error: $exception");
            },
          ),
        ),
        child: Padding(
          padding: EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(height: 20),
              Card(
                elevation: 6,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                child: Padding(
                  padding: EdgeInsets.all(24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('MONTH: $currentMonth', style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold, fontSize: 18)),
                      SizedBox(height: 12),
                      Text("Total Income: \$${totalIncome.toStringAsFixed(2)}", style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                      SizedBox(height: 12),
                      Text("Remaining Balance: \$${remainingBalance.toStringAsFixed(2)}", style: TextStyle(fontSize: 20, color: Colors.green, fontWeight: FontWeight.bold)),
                    ],
                  ),
                ),
              ),
              SizedBox(height: 20),
              LinearProgressIndicator(
                value: totalIncome == 0 ? 0 : spentAmount / totalIncome,
                backgroundColor: Colors.grey[300],
                color: Colors.red,
                minHeight: 15,
              ),
              SizedBox(height: 10),
              Text("Spent: \$${spentAmount.toStringAsFixed(2)} / \$${totalIncome.toStringAsFixed(2)}", style: TextStyle(fontSize: 18, color: Colors.orangeAccent, fontWeight: FontWeight.bold)),
              SizedBox(height: 30),
              // Buttons
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  ElevatedButton(
                    onPressed: () async {
                      final result = await Navigator.pushNamed(context, '/add_income');
                      if (result != null) {
                        double newIncome = result as double;
                        updateIncome(newIncome);
                      }
                    },
                    child: Text("Add Income", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 24)),
                    style: ElevatedButton.styleFrom(
                      padding: EdgeInsets.symmetric(horizontal: 30, vertical: 30),
                      backgroundColor: Colors.deepPurple[800], // Replace primary with backgroundColor
                    ),
                  ),
                  SizedBox(width: 20),
                  ElevatedButton(
                    onPressed: () async {
                      final result = await Navigator.pushNamed(context, '/add_expense');
                      if (result != null) {
                        Map<String, dynamic> expenseData = result as Map<String, dynamic>;
                        addExpense(expenseData['category'], expenseData['amount']);
                      }
                    },
                    child: Text("Add Expense", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 24)),
                    style: ElevatedButton.styleFrom(
                      padding: EdgeInsets.symmetric(horizontal: 30, vertical: 30),
                      backgroundColor: Colors.deepPurple[800], // Replace primary with backgroundColor
                    ),
                  ),
                ],
              ),
              SizedBox(height: 20),
              // Updated Expenses List
              Expanded(
                child: ListView(
                  children: categoryExpenses.entries.map((entry) {
                    return Container(
                      margin: EdgeInsets.symmetric(vertical: 10),
                      padding: EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(15),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(entry.key, style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white)),
                          Text("\$${entry.value.toStringAsFixed(2)}", style: TextStyle(fontSize: 18, color: Colors.green, fontWeight: FontWeight.bold)),
                        ],
                      ),
                    );
                  }).toList(),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
