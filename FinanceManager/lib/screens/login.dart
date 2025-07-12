import 'package:flutter/material.dart';
import 'package:financemanager/models/auth_method.dart';


class Login extends StatefulWidget {
  const Login({super.key});

  @override
  State<Login> createState() => _LoginState();
}

class _LoginState extends State<Login> {
  TextEditingController _emailController = TextEditingController();
  TextEditingController _passwordController = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  final AuthMethod _authMethod = AuthMethod();

  @override
  void dispose() {
    super.dispose();
    _emailController.dispose();
    _passwordController.dispose();
  }

  String? _validateEmail(String? value) {
    if (value == null || value.isEmpty) {
      return 'Please enter your email';
    }
    final emailRegex = RegExp(r'^[^@]+@[^@]+\.[^@]+');
    if (!emailRegex.hasMatch(value)) {
      return 'Please enter a valid email address';
    }
    return null;
  }

  String? _validatePassword(String? value) {
    if (value == null || value.isEmpty) {
      return 'Please enter a password';
    }
    if (value.length < 6) {
      return 'Password must be at least 6 characters long';
    }
    return null;
  }

  void _login() async {
    if (_formKey.currentState!.validate()) {
      String email = _emailController.text.trim();
      String password = _passwordController.text.trim();

      String res = await _authMethod.loginUser(email: email, password: password);

      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(res)));

      if (res == 'Login Successful') {
        Navigator.pushReplacementNamed(context, '/dashboard');
      }
    }
  }


  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        margin: EdgeInsets.only(left: 10, right: 10, top: 60),
        child: Form(
          key: _formKey,
          child: Column(
            children: [
              Text('Login', style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold, fontSize: 27)),
              SizedBox(height: 9),
              Text('Sign in to your account', style: TextStyle(color: Colors.black38, fontSize: 20)),
              SizedBox(height: 25),
              _buildTextField(_emailController, 'Email', Icons.email, _validateEmail),
              SizedBox(height: 25),
              _buildTextField(_passwordController, 'Password', Icons.lock, _validatePassword, obscureText: true),
              SizedBox(height: 25),
              GestureDetector(
                onTap: _login,
                child: _buildActionButton('Login'),
              ),
              SizedBox(
                height:10,
              ),
              GestureDetector(
                onTap: () {
                  Navigator.pushReplacementNamed(context, '/signup');
                },

                child: Text(
                  "Don't have an account? Sign Up",
                  style: TextStyle(fontSize: 16, color: Colors.purple),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTextField(TextEditingController controller, String hint, IconData icon, String? Function(String?)? validator, {bool obscureText = false}) {
    return Container(
      margin: EdgeInsets.symmetric(horizontal: 20),
      padding: EdgeInsets.symmetric(vertical: 14),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(14),
        color: Colors.grey,
      ),
      child: TextFormField(
        controller: controller,
        obscureText: obscureText,
        validator: validator,
        decoration: InputDecoration(
          icon: Icon(icon, color: Colors.black),
          hintText: hint,
          border: InputBorder.none,
          contentPadding: EdgeInsets.symmetric(horizontal: 10),
        ),
      ),
    );
  }

  Widget _buildActionButton(String text) {
    return Container(
      margin: EdgeInsets.symmetric(horizontal: 20),
      padding: EdgeInsets.symmetric(vertical: 23),
      decoration: BoxDecoration(color: Colors.purple, borderRadius: BorderRadius.circular(16)),
      child: Center(child: Text(text, style: TextStyle(color: Colors.white, fontSize: 21))),
    );
  }
}
