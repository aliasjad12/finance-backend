import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class SavedSavingsPlansScreen extends StatefulWidget {
  @override
  _SavedSavingsPlansScreenState createState() => _SavedSavingsPlansScreenState();
}

class _SavedSavingsPlansScreenState extends State<SavedSavingsPlansScreen> {
  String? userId;
  String currentMonth = "";
  List<Map<String, dynamic>> goals = [];

  @override
  void initState() {
    super.initState();
    userId = FirebaseAuth.instance.currentUser?.uid;
    currentMonth = getCurrentMonth();
    fetchGoals();
  }

  String getCurrentMonth() {
    DateTime now = DateTime.now();
    return "${now.year}-${now.month.toString().padLeft(2, '0')}";
  }

  Future<void> fetchGoals() async {
    if (userId == null) return;
    try {
      final snapshot = await FirebaseFirestore.instance
          .collection('users')
          .doc(userId)
          .collection('records')
          .doc(currentMonth)
          .collection('savings_goals')
          .get();

      final loadedGoals = snapshot.docs.map((doc) {
        final data = doc.data();
        data['id'] = doc.id;
        return data;
      }).toList();

      setState(() {
        goals = loadedGoals.cast<Map<String, dynamic>>();
      });
    } catch (e) {
      print("Error fetching goals: $e");
    }
  }

  Future<void> deleteGoal(String goalId) async {
    if (userId == null) return;
    try {
      final ref = FirebaseFirestore.instance
          .collection('users')
          .doc(userId)
          .collection('records')
          .doc(currentMonth)
          .collection('savings_goals')
          .doc(goalId);

      await ref.delete();
      fetchGoals(); // Reload goals after deletion
    } catch (e) {
      print("Error deleting goal: $e");
    }
  }

  Future<void> updateGoal(String goalId, Map<String, dynamic> updatedData) async {
    if (userId == null) return;
    try {
      final ref = FirebaseFirestore.instance
          .collection('users')
          .doc(userId)
          .collection('records')
          .doc(currentMonth)
          .collection('savings_goals')
          .doc(goalId);

      await ref.update(updatedData);
      fetchGoals();
    } catch (e) {
      print("Error updating goal: $e");
    }
  }

  Future<String> fetchSuggestion(String goalId) async {
    try {
      final url = Uri.parse("http://192.168.1.183:5000/track_goal_progress?user_id=$userId&goal_id=$goalId&current_month=$currentMonth");
      final response = await http.get(url);
      if (response.statusCode == 200) {
        final jsonData = json.decode(response.body);
        return jsonData['suggestion'] ?? 'No suggestion';
      } else {
        return 'Error fetching suggestion';
      }
    } catch (e) {
      print("Error: $e");
      return 'Suggestion error';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Color(0xFFF5F6FA),
      appBar: AppBar(
        title: Text("Saved Savings Goals", style: TextStyle(fontWeight: FontWeight.bold)),
        centerTitle: true,
        backgroundColor: Colors.teal,
        elevation: 4,
      ),
      body: goals.isEmpty
          ? Center(
        child: Text(
          "No saved plans",
          style: TextStyle(fontSize: 18, color: Colors.grey),
        ),
      )
          : ListView.builder(
        padding: EdgeInsets.all(12),
        itemCount: goals.length,
        itemBuilder: (context, index) {
          final goal = goals[index];
          final TextEditingController savedController =
          TextEditingController(text: goal['amount_saved'].toString());
          final TextEditingController targetController =
          TextEditingController(text: goal['target_amount'].toString());

          return Card(
            elevation: 6,
            margin: EdgeInsets.symmetric(vertical: 10),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            child: Padding(
              padding: EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    "🎯 Goal: ${goal['goal_name']}",
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18, color: Colors.deepPurple),
                  ),
                  SizedBox(height: 16),
                  TextField(
                    controller: savedController,
                    decoration: InputDecoration(
                      labelText: "Amount Saved",
                      prefixIcon: Icon(Icons.savings),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                      filled: true,
                      fillColor: Colors.grey[100],
                    ),
                    keyboardType: TextInputType.number,
                    onSubmitted: (value) {
                      final updatedAmount = double.tryParse(value) ?? 0;
                      final progress = (updatedAmount / (goal['target_amount'] ?? 1)) * 100;
                      updateGoal(goal['id'], {
                        'amount_saved': updatedAmount,
                        'progress_percentage': progress,
                      });
                    },
                  ),
                  SizedBox(height: 12),
                  TextField(
                    controller: targetController,
                    decoration: InputDecoration(
                      labelText: "Target Amount",
                      prefixIcon: Icon(Icons.flag),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                      filled: true,
                      fillColor: Colors.grey[100],
                    ),
                    keyboardType: TextInputType.number,
                    onSubmitted: (value) {
                      final updatedTarget = double.tryParse(value) ?? 1;
                      final progress = (goal['amount_saved'] / updatedTarget) * 100;
                      updateGoal(goal['id'], {
                        'target_amount': updatedTarget,
                        'progress_percentage': progress,
                      });
                    },
                  ),
                  SizedBox(height: 16),
                  FutureBuilder(
                    future: fetchSuggestion(goal['id']),
                    builder: (context, snapshot) {
                      if (snapshot.connectionState == ConnectionState.waiting) {
                        return Row(
                          children: [
                            CircularProgressIndicator(),
                            SizedBox(width: 12),
                            Text("Loading suggestion..."),
                          ],
                        );
                      } else if (snapshot.hasError) {
                        return Text("❌ Error loading suggestion");
                      } else {
                        return Text(
                          "💡 Suggestion: ${snapshot.data}",
                          style: TextStyle(color: Colors.green[700], fontStyle: FontStyle.italic),
                        );
                      }
                    },
                  ),
                  SizedBox(height: 12),
                  // Delete Button
                  ElevatedButton(
                    onPressed: () {
                      showDialog(
                        context: context,
                        builder: (BuildContext context) {
                          return AlertDialog(
                            title: Text("Delete Goal"),
                            content: Text("Are you sure you want to delete this goal?"),
                            actions: [
                              TextButton(
                                onPressed: () {
                                  Navigator.pop(context);
                                },
                                child: Text("Cancel"),
                              ),
                              TextButton(
                                onPressed: () async {
                                  await deleteGoal(goal['id']);
                                  Navigator.pop(context);
                                },
                                child: Text("Delete"),
                              ),
                            ],
                          );
                        },
                      );
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.red, // Use backgroundColor instead of primary
                    ),
                    child: Text("Delete Goal", style: TextStyle(color: Colors.white)),
                  ),

                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
