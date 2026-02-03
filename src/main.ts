import "./style.css";
import { AppController } from "./app/AppController";

const app = new AppController();
app.init().catch(console.error);