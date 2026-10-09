import Foundation

enum Value: Codable, Hashable {
    case string(String), number(Double), bool(Bool), array([Value]), object([String: Value]), null
    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .null }
        else if let v = try? c.decode(Bool.self) { self = .bool(v) }
        else if let v = try? c.decode(Double.self) { self = .number(v) }
        else if let v = try? c.decode(String.self) { self = .string(v) }
        else if let v = try? c.decode([Value].self) { self = .array(v) }
        else { self = .object(try c.decode([String: Value].self)) }
    }
    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .string(let v): try c.encode(v)
        case .number(let v): try c.encode(v)
        case .bool(let v): try c.encode(v)
        case .array(let v): try c.encode(v)
        case .object(let v): try c.encode(v)
        case .null: try c.encodeNil()
        }
    }
    var text: String {
        switch self {
        case .string(let v): return v
        case .number(let v): return v == v.rounded() ? String(format: "%.0f", v) : String(v)
        case .bool(let v): return v ? "Tak" : "Nie"
        case .null: return "—"
        case .array(let v): return v.map(\.text).joined(separator: ", ")
        case .object(let values): return values.keys.sorted().map { "\($0): \(values[$0]?.text ?? "—")" }.joined(separator: "\n")
        }
    }
}
struct User: Decodable { let id: String; let name: String; let role: String }
struct Permission: Decodable { let read: Bool; let write: Bool }
struct Profile: Decodable { let user: User; let school: String; let apps: [String]; let permissions: [String: Permission] }
struct LoginReply: Decodable { let token: String }
struct Row: Codable, Identifiable { let id: String; let version: Int; let data: [String: Value] }
struct AppInfo: Decodable, Identifiable { let id: String; let name: String; let modules: [String] }
struct Field: Decodable, Identifiable {
    let key: String; let label: String; let kind: String; let options: [String]; let required: Bool
    var id: String { key }
}
struct Resource: Decodable, Identifiable { let id: String; let name: String; let fields: [Field] }
struct Catalog: Decodable {
    let apps: [AppInfo]; let resources: [Resource]; let roles: [String: String]
    static let shared: Catalog = {
        guard let url = Bundle.main.url(forResource: "Catalog", withExtension: "json"),
              let data = try? Data(contentsOf: url), let catalog = try? JSONDecoder().decode(Catalog.self, from: data)
        else { fatalError("Brak katalogu aplikacji") }
        return catalog
    }()
    func resource(_ id: String) -> Resource { resources.first { $0.id == id }! }
}
struct Choice: Identifiable { let id: String; let name: String }
struct APIError: LocalizedError {
    let status: Int; let message: String
    var errorDescription: String? { message }
}
