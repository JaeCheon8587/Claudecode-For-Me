using System;
using System.Collections.Generic;

namespace OMS.Core.Messaging
{
    public interface IEventBus
    {
        void Publish<T>(T @event);
        void Subscribe<T>(Action<T> handler);
    }

    /// <summary>
    /// 인메모리 이벤트 버스. 도메인 이벤트를 발행하고 구독자에게 디스패치.
    /// </summary>
    public class InMemoryEventBus : IEventBus
    {
        private readonly Dictionary<Type, List<object>> _handlers = new();

        public void Publish<T>(T @event)
        {
            var type = typeof(T);
            if (!_handlers.TryGetValue(type, out var list)) return;
            foreach (var h in list) ((Action<T>)h)(@event);
        }

        public void Subscribe<T>(Action<T> handler)
        {
            var type = typeof(T);
            if (!_handlers.ContainsKey(type)) _handlers[type] = new();
            _handlers[type].Add(handler);
        }

        public void Clear() => _handlers.Clear();
    }
}
