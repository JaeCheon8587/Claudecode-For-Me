using System.Collections.Generic;
using System.Threading.Tasks;

namespace OMS.Infrastructure.Persistence
{
    /// <summary>
    /// 주문 데이터를 SQL Server에 저장하고 조회하는 리포지터리.
    /// </summary>
    public class OrderRepository : IOrderRepository
    {
        private readonly IDbContext _db;

        public OrderRepository(IDbContext db)
        {
            _db = db;
        }

        public async Task<Order> GetByIdAsync(int id) => await _db.Orders.FindAsync(id);

        public async Task SaveAsync(Order order) => await _db.SaveChangesAsync();

        public async Task<List<Order>> GetPendingAsync() =>
            await _db.Orders.Where(o => o.Status == OrderStatus.Pending).ToListAsync();
    }

    public interface IOrderRepository
    {
        Task<Order> GetByIdAsync(int id);
        Task SaveAsync(Order order);
    }
}
