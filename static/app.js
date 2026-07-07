// ==========================================
// TradingBot V4
// app.js
// ==========================================

async function loadStatus() {

    try {

        const res = await fetch("/api/status");

        const data = await res.json();

        document.getElementById("balance").innerHTML =
            data.balance.toFixed(2);

        document.getElementById("pnl").innerHTML =
            data.session_pnl.toFixed(2);

        document.getElementById("wr").innerHTML =
            data.win_rate.toFixed(1) + "%";

        document.getElementById("trades").innerHTML =
            data.trades;

        document.getElementById("cpu").innerHTML =
            data.cpu + "%";

        document.getElementById("ram").innerHTML =
            data.ram + " MB";

        document.getElementById("uptime").innerHTML =
            data.uptime;

        document.getElementById("botstatus").innerHTML =
            data.status;

        let txt = "";

        if (data.positions.length === 0) {

            txt = "No Open Positions";

        } else {

            data.positions.forEach(function(p){

                txt +=
                    "<p><b>" +
                    p.symbol +
                    "</b> - " +
                    p.side +
                    "</p>";

            });

        }

        document.getElementById("positions").innerHTML =
            txt;

    }

    catch(e){

        console.log(e);

    }

}

loadStatus();

setInterval(loadStatus,5000);
