using System;
using System.Collections.Generic;

namespace OMS.Core.Collectors
{
    /// <summary>
    /// PLC에서 센서 데이터를 주기 폴링·버퍼링 후 EventBus로 송출하는 수집기.
    /// </summary>
    public class DataCollector : IDisposable
    {
        private readonly IEventBus _bus;
        private readonly List<SensorData> _buffer = new();

        public DataCollector(IEventBus bus)
        {
            _bus = bus;
        }

        public void Poll(string plcAddress, int timeoutMs = 1000)
        {
            // 주기 PLC 호출
        }

        public void Flush()
        {
            // 버퍼 강제 송출
        }

        public void Dispose() { }
    }

    public class SensorData
    {
        public string Tag { get; set; } = "";
        public double Value { get; set; }
        public DateTime Timestamp { get; set; }

        public bool IsValid() => Value >= 0;
        public string Serialize() => $"{Tag}={Value}@{Timestamp:O}";
    }
}
