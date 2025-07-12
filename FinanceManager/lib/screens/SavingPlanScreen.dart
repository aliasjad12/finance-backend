import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';

class SavingsPlanScreen extends StatefulWidget {
  @override
  _SavingsPlanScreenState createState() => _SavingsPlanScreenState();
}

class _SavingsPlanScreenState extends State<SavingsPlanScreen> {
  String goalName = '';
  double targetAmount = 0;
  String? userId;
  String currentMonth = "";

  @override
  void initState() {
    super.initState();
    userId = FirebaseAuth.instance.currentUser?.uid;
    currentMonth = getCurrentMonth();
  }

  String getCurrentMonth() {
    DateTime now = DateTime.now();
    return "${now.year}-${now.month.toString().padLeft(2, '0')}";
  }

  Future<void> addSavingsGoal() async {
    if (userId == null || goalName.isEmpty || targetAmount == 0) return;

    try {
      DocumentReference recordRef = FirebaseFirestore.instance
          .collection('users')
          .doc(userId)
          .collection('records')
          .doc(currentMonth);

      await recordRef.set({'createdAt': FieldValue.serverTimestamp()}, SetOptions(merge: true));

      await recordRef.collection('savings_goals').add({
        'goal_name': goalName,
        'target_amount': targetAmount,
        'amount_saved': 0,
        'progress_percentage': 0,
        'start_date': DateTime.now().toIso8601String(),
      });

      setState(() {
        goalName = '';
        targetAmount = 0;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Goal added successfully'),
          backgroundColor: Colors.green.shade600,
        ),
      );
    } catch (e) {
      print("Error adding goal: $e");
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text("Add Savings Goal", style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: Colors.teal,
        elevation: 0,
      ),
      body: Container(
        padding: EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: Colors.grey.shade100,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              "Create a new savings goal",
              style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),

            ),
            SizedBox(height: 20),
            TextField(
              decoration: InputDecoration(
                labelText: "Goal Name",
                filled: true,
                fillColor: Colors.white,
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
              onChanged: (value) => setState(() => goalName = value),
            ),
            SizedBox(height: 16),
            TextField(
              decoration: InputDecoration(
                labelText: "Target Amount",
                filled: true,
                fillColor: Colors.white,
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
              keyboardType: TextInputType.number,
              onChanged: (value) => setState(() => targetAmount = double.tryParse(value) ?? 0),
            ),
            SizedBox(height: 30),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: addSavingsGoal,
                icon: Icon(Icons.add_task_rounded),
                label: Text("Add Goal", style: TextStyle(fontSize: 16)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.teal.shade700,
                  padding: EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
              ),
            ),
            SizedBox(height: 10),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () {
                  Navigator.pushNamed(context, '/saved_savings_plans');
                },
                icon: Icon(Icons.list_alt_rounded, color: Colors.teal.shade800),
                label: Text("View All Saved Plans", style: TextStyle(fontSize: 16, color: Colors.teal.shade800)),
                style: OutlinedButton.styleFrom(
                  side: BorderSide(color: Colors.teal.shade600),
                  padding: EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
