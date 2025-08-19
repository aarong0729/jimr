# 🚀 Jim Rohn AI Coach - Deployment Guide

Deploy your multi-user Jim Rohn AI Coach to the cloud so friends can access it anywhere!

## 📋 Prerequisites

1. **GitHub Account** (free)
2. **Railway Account** (free tier available)
3. **API Keys**:
   - OpenAI API key
   - ElevenLabs API key (optional, for voice)
   - Jim Rohn voice ID from ElevenLabs

## 🔧 Step 1: Setup GitHub Repository

1. **Create a new repository** on GitHub:
   - Go to https://github.com/new
   - Repository name: `jim-rohn-ai-coach`
   - Make it **private** (contains API keys)
   - Create repository

2. **Upload your files**:
   ```bash
   cd /Users/goodin/Desktop/jim
   git init
   git add jim_server_multiuser.py
   git add requirements_production.txt
   git add Procfile
   git add runtime.txt
   git add .env.example
   git add .gitignore
   git add jim_rohn_materials/
   git add jim_rohn_system.py
   git add "System prompt.txt"
   git commit -m "Initial commit - Jim Rohn AI Coach"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/jim-rohn-ai-coach.git
   git push -u origin main
   ```

## 🚄 Step 2: Deploy to Railway

1. **Sign up for Railway**:
   - Go to https://railway.app
   - Sign up with your GitHub account

2. **Create new project**:
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your `jim-rohn-ai-coach` repository

3. **Configure Environment Variables**:
   In Railway dashboard, go to Variables tab and add:
   ```
   OPENAI_API_KEY=sk-your-actual-openai-key-here
   ELEVENLABS_API_KEY=your-actual-elevenlabs-key-here
   JIM_ROHN_VOICE_ID=your-actual-voice-id-here
   ADMIN_PASSWORD=create-a-secure-admin-password
   SECRET_KEY=generate-a-random-secret-key
   PORT=5001
   ```

4. **Deploy**:
   - Railway will automatically detect the Procfile
   - Deployment will start automatically
   - Wait for "Deployed" status

## 🌐 Step 3: Get Your URL

1. In Railway dashboard, click "Generate Domain"
2. Your app will be available at: `https://your-app-name.railway.app`
3. Test it by visiting the URL

## 👥 Step 4: Share with Friends

**Send them**:
- The URL: `https://your-app-name.railway.app`
- Instructions to register an account
- Let them know it's free to use!

**You have admin access**:
- Admin dashboard: `https://your-app-name.railway.app/admin`
- Password: whatever you set as `ADMIN_PASSWORD`
- Update knowledge base when you add new content

## 💰 Costs

- **Railway**: $5/month after free tier
- **OpenAI API**: ~$0.02 per conversation
- **ElevenLabs**: ~$0.30 per minute of voice (optional)

## 🔄 Updating Content

1. **Add new Jim Rohn content**:
   - Add .txt files to `jim_rohn_materials/` folder
   - Commit and push to GitHub
   - Railway will auto-deploy

2. **Update knowledge base**:
   - Go to admin dashboard
   - Click "Update Knowledge Base"
   - New content is now searchable!

## 🛡️ Security Features

- ✅ Individual user accounts
- ✅ Secure password hashing
- ✅ Private conversation histories
- ✅ Admin-only content updates
- ✅ Session management

## 🆘 Troubleshooting

**App won't start?**
- Check environment variables are set correctly
- Look at Railway logs for error messages

**Users can't register?**
- Check the logs for database errors
- Ensure proper file permissions

**Knowledge base not updating?**
- Verify all .txt files are in `jim_rohn_materials/`
- Check admin password is correct

**Need help?**
- Check Railway logs in the dashboard
- Contact support or check the issues

## 🎉 You're Done!

Your friends can now:
1. Visit your URL
2. Create accounts
3. Chat with Jim Rohn
4. Each person gets their own memory/history
5. Jim remembers their name and details!

You can add new content anytime through the admin dashboard!