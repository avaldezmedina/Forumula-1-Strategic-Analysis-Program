import type { InterpolatedCar } from "../hooks/usePlaybackEngine";
import type { ReplayDriver } from "../types";

interface LeaderboardProps {
  cars: InterpolatedCar[];
  drivers: ReplayDriver[];
}

export function Leaderboard({ cars, drivers }: LeaderboardProps) {
  const driverMap = new Map(drivers.map((driver) => [driver.driver_number, driver]));

  return (
    <div className="leaderboard">
      <h3>Leaderboard</h3>
      <table>
        <thead>
          <tr>
            <th>Pos</th>
            <th>Driver</th>
            <th>Gap</th>
          </tr>
        </thead>
        <tbody>
          {cars.map((car) => {
            const driver = driverMap.get(car.driverNumber);
            return (
              <tr key={car.driverNumber}>
                <td>{car.position ?? "-"}</td>
                <td>
                  <span
                    className="team-dot"
                    style={{ backgroundColor: driver?.team_color ?? "#fff" }}
                  />
                  {driver?.name ?? car.driverNumber}
                </td>
                <td>{car.interval ?? (car.position === 1 ? "Leader" : "-")}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
