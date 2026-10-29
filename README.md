# 🚌 SmartBus — Smart Bus Recommendation System

SmartBus is a smart bus recommendation system designed to help passengers find suitable buses based on their source, destination, preferred bus type, and travel time. It helps users compare available buses, check fares and timings, and identify faster travel options to reduce unnecessary waiting and make daily commuting more convenient.

## 📌 Project Overview

Finding the right bus can be difficult when passengers need to travel between intermediate stops or want to catch a bus at a specific time. SmartBus addresses this problem by providing route-based bus recommendations using structured bus, route, stop, timing, and fare data stored in MongoDB.

The system focuses on making bus selection easier by considering the passenger's travel requirements and presenting relevant bus options.

## 🎯 Objectives

- Find buses between a selected source and destination.
- Filter buses by type, including AC and Non-AC.
- Display buses according to the preferred travel time.
- Show relevant bus timings and fares.
- Recommend faster and more convenient bus options.
- Support passengers travelling between intermediate stops.
- Reduce unnecessary waiting and improve travel planning.

## ✨ Key Features

- **Smart Bus Search:** Search for buses using source and destination stops.
- **Time-Based Filtering:** Find buses within the selected travel-time window.
- **Bus Type Filtering:** Choose between AC and Non-AC buses.
- **Fare Information:** View fares for different source-destination pairs.
- **Route Information:** Explore intermediate stops along a bus route.
- **Fastest Bus Recommendation:** Identify suitable options based on estimated journey duration and route information.
- **Intermediate Stop Search:** Find buses serving stops between major destinations.
- **MongoDB Database:** Store and retrieve bus, route, stop, timing, trip, and fare information.

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| HTML5 | Structure of the web application |
| CSS3 | Styling and responsive user interface |
| JavaScript | Search logic, filtering, and recommendations |
| MongoDB | Database for storing bus and route information |
| Node.js | Backend runtime |
| Express.js | Backend API and server-side operations |

## 🗂️ Database Structure

SmartBus uses a MongoDB database named `smartbus`.

The project contains the following collections:

| Collection | Description |
|---|---|
| `buses` | Bus names, operators, and bus types |
| `stops` | Stop IDs and stop names |
| `trips` | Trip details, bus references, and travel directions |
| `routes` | Ordered stops along each trip |
| `stop_times` | Arrival and departure timing information |
| `fares` | Fare information for source-destination pairs and bus types |

### Dataset Summary

The current verified dataset contains:

- **95 buses**
- **95 trips**
- **9 stops**
- **676 route records**
- **676 stop-time records**
- **128 fare records**

These counts describe the dataset at the last database verification and may change as the project develops.

## 🧭 How SmartBus Works

1. The passenger selects a source and destination.
2. The passenger chooses a preferred bus type and travel time.
3. The application retrieves relevant trips and route information from MongoDB.
4. The system checks whether the selected destination appears after the source in the trip's stop sequence.
5. Matching buses are filtered according to the selected time and bus type.
6. The application displays relevant bus details, route information, and available fare data.
7. Suitable options can be compared to identify a faster or more convenient journey.

## 💡 Example Use Case

Suppose a student wants to travel from LPU to Goraya after college.

Instead of waiting at the bus stop without knowing when a suitable bus will arrive, the student can:

1. Select **LPU** as the source.
2. Select **Goraya** as the destination.
3. Choose AC or Non-AC.
4. Enter a preferred time, such as 3:00 PM.
5. View matching buses operating within the selected time window.
6. Compare their timings, fares, and routes before choosing a suitable bus.

This helps the student make a more informed travel decision.

## 📁 Project Structure

The project can be organized as follows:

```text
SmartBus/
│
├── public/
│   ├── index.html
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── script.js
│
├── routes/
│   └── busRoutes.js
│
├── models/
│   └── databaseModels.js
│
├── config/
│   └── db.js
│
├── server.js
├── package.json
├── .gitignore
└── README.md
```

*Note: This is a suggested structure. Adjust it to match the actual files in your repository.*

## ⚙️ Installation and Setup

### Prerequisites

- Node.js and npm
- MongoDB Community Server
- A web browser
- Git (optional)

### 1. Clone the Repository

```bash
git clone <your-github-repository-url>
cd SmartBus
```

### 2. Install Dependencies

```bash
npm install
```

### 3. Configure MongoDB

Start your local MongoDB server and ensure that the `smartbus` database contains the required collections.

A typical local MongoDB connection string is:

```text
mongodb://127.0.0.1:27017/smartbus
```

Configure the connection string in your environment variables or database configuration file as required by your application.

### 4. Start the Application

```bash
npm start
```

If your project uses a different startup script, use the command configured in `package.json`.

Open the local URL printed by your server in the browser.

## 🚀 Future Enhancements

- Live bus location tracking using GPS.
- Real-time arrival predictions.
- User registration and saved routes.
- Interactive route maps.
- Notifications for upcoming buses.
- Improved recommendations using historical travel data.
- Mobile-friendly interface and accessibility improvements.

## 🎓 Project Purpose

SmartBus is developed as a final-year academic project to demonstrate the practical application of database management, web development, route-based data retrieval, and recommendation logic to a real-world transportation problem.

## 👨‍💻 Author

**Mayank Thakur**

Computer Science and Engineering

## 📄 License

This project is developed for educational and academic purposes. Add an appropriate open-source license if you intend to distribute or reuse the project publicly.
